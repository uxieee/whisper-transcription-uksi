"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { formatClockTime, segmentsToSrt, type TranscriptSegment } from "@/lib/transcript";

type WorkerStatusMessage = {
  type: "status";
  requestId: string;
  stage: "loading" | "running" | "ready";
  message: string;
};

type WorkerCompleteMessage = {
  type: "complete";
  requestId: string;
  text?: string;
  chunks?: Array<{
    text?: string;
    timestamp?: [number | null, number | null] | null;
  }>;
};

type WorkerErrorMessage = {
  type: "error";
  requestId: string;
  message: string;
};

type WorkerMessage = WorkerStatusMessage | WorkerCompleteMessage | WorkerErrorMessage;

type TranscriptionResult = {
  text: string;
  srt: string;
  segments: TranscriptSegment[];
  metadata: {
    fileName: string;
    model: string;
    language: string | null;
    durationSeconds: number | null;
    runtime: "browser-worker";
  };
};

type ActiveRequest = {
  id: string;
  fileName: string;
  model: string;
  language: string | null;
};

type DecodedAudio = {
  samples: Float32Array;
  sampleRate: number;
};

type RecentStatus = "processing" | "completed" | "failed" | "draft";

type RecentTranscription = {
  id: string;
  fileName: string;
  status: RecentStatus;
  updatedAt: number;
  model: string;
  language: string | null;
  result?: TranscriptionResult;
  demo?: boolean;
};

const languageOptions = [
  { value: "", label: "Auto detect" },
  { value: "en", label: "English" },
  { value: "tl", label: "Tagalog" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "ja", label: "Japanese" },
  { value: "ko", label: "Korean" }
];

const modelOptions = [
  { value: "Xenova/whisper-tiny", label: "Whisper Tiny (fastest)" },
  { value: "Xenova/whisper-tiny.en", label: "Whisper Tiny.en (English-only)" },
  { value: "Xenova/whisper-base", label: "Whisper Base" },
  { value: "Xenova/whisper-base.en", label: "Whisper Base.en (English-only)" },
  { value: "Xenova/whisper-small", label: "Whisper Small" },
  { value: "Xenova/whisper-small.en", label: "Whisper Small.en (English-only)" },
  { value: "Xenova/whisper-medium", label: "Whisper Medium" },
  { value: "Xenova/whisper-medium.en", label: "Whisper Medium.en (English-only)" },
  { value: "Xenova/whisper-large-v1", label: "Whisper Large (v1)" },
  { value: "Xenova/whisper-large-v2", label: "Whisper Large (v2)" },
  { value: "Xenova/whisper-large-v3", label: "Whisper Large-v3" },
  { value: "onnx-community/whisper-large-v3-turbo", label: "Whisper Large-v3 Turbo" }
];

const demoRecentItems: RecentTranscription[] = [
  {
    id: "demo-completed",
    fileName: "Interview_with_CEO.mp3",
    status: "completed",
    updatedAt: Date.now() - 2 * 60 * 1000,
    model: "Xenova/whisper-small",
    language: "en",
    demo: true
  },
  {
    id: "demo-processing",
    fileName: "Team_Meeting_Oct24.wav",
    status: "processing",
    updatedAt: Date.now() - 35 * 1000,
    model: "Xenova/whisper-medium",
    language: "en",
    demo: true
  },
  {
    id: "demo-draft",
    fileName: "Podcast_Episode_05.mp3",
    status: "draft",
    updatedAt: Date.now() - 24 * 60 * 60 * 1000,
    model: "Xenova/whisper-base",
    language: null,
    demo: true
  }
];

function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function normalizeChunkSegments(chunks: WorkerCompleteMessage["chunks"]): TranscriptSegment[] {
  if (!Array.isArray(chunks)) {
    return [];
  }

  return chunks
    .map((chunk) => {
      if (!chunk || typeof chunk !== "object") {
        return null;
      }

      const text = typeof chunk.text === "string" ? chunk.text.trim() : "";
      if (!text) {
        return null;
      }

      const timestamp = Array.isArray(chunk.timestamp) ? chunk.timestamp : [0, 0];
      const start = Number(timestamp[0] ?? 0);
      const endRaw = Number(timestamp[1] ?? start);

      if (!Number.isFinite(start) || !Number.isFinite(endRaw)) {
        return null;
      }

      return {
        start: Math.max(0, start),
        end: Math.max(start, endRaw),
        text
      } satisfies TranscriptSegment;
    })
    .filter((segment): segment is TranscriptSegment => Boolean(segment));
}

function mergeChannels(buffer: AudioBuffer): Float32Array {
  if (buffer.numberOfChannels === 1) {
    return buffer.getChannelData(0).slice();
  }

  const merged = new Float32Array(buffer.length);
  for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let index = 0; index < data.length; index += 1) {
      merged[index] += data[index] / buffer.numberOfChannels;
    }
  }

  return merged;
}

async function decodeAudioFile(file: File): Promise<DecodedAudio> {
  if (typeof window === "undefined") {
    throw new Error("This browser environment is not available for local decoding.");
  }

  const audioContextConstructor =
    window.AudioContext ||
    (window as typeof window & { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;

  if (!audioContextConstructor) {
    throw new Error("This browser does not support AudioContext decoding.");
  }

  const context = new audioContextConstructor();

  try {
    const arrayBuffer = await file.arrayBuffer();
    const decoded = await context.decodeAudioData(arrayBuffer.slice(0));

    return {
      samples: mergeChannels(decoded),
      sampleRate: decoded.sampleRate
    };
  } finally {
    await context.close();
  }
}

function formatUpdatedAt(timestamp: number): string {
  return new Date(timestamp).toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit"
  });
}

function getStatusLine(item: RecentTranscription): string {
  if (item.status === "processing") {
    return "Processing...";
  }

  if (item.status === "completed") {
    return `Completed • ${formatUpdatedAt(item.updatedAt)}`;
  }

  if (item.status === "failed") {
    return `Failed • ${formatUpdatedAt(item.updatedAt)}`;
  }

  return `Draft • ${formatUpdatedAt(item.updatedAt)}`;
}

function buildTimestampedTranscript(segments: TranscriptSegment[]): string {
  return segments
    .map((segment) => `[${formatClockTime(segment.start)} - ${formatClockTime(segment.end)}] ${segment.text}`)
    .join("\n");
}

export function TranscriptionStudio() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const workerRef = useRef<Worker | null>(null);
  const activeRequestRef = useRef<ActiveRequest | null>(null);

  const [activeFile, setActiveFile] = useState<File | null>(null);
  const [selectedModel, setSelectedModel] = useState(modelOptions[0].value);
  const [language, setLanguage] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusText, setStatusText] = useState(
    "Drop an audio file to begin. Transcription runs locally in your browser."
  );
  const [errorText, setErrorText] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptionResult | null>(null);
  const [recentItems, setRecentItems] = useState<RecentTranscription[]>([]);

  const activeResult = result;

  const fileSizeLabel = useMemo(() => {
    if (!activeFile) {
      return "No file selected yet";
    }

    return `${activeFile.name} • ${(activeFile.size / 1024 / 1024).toFixed(2)} MB`;
  }, [activeFile]);

  const renderedRecentItems = useMemo(() => (recentItems.length > 0 ? recentItems : demoRecentItems), [recentItems]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const worker = new Worker(new URL("./whisper.worker.ts", import.meta.url));
    workerRef.current = worker;

    worker.onmessage = (event: MessageEvent<WorkerMessage>) => {
      const message = event.data;
      const activeRequest = activeRequestRef.current;
      if (!activeRequest || message.requestId !== activeRequest.id) {
        return;
      }

      if (message.type === "status") {
        setStatusText(message.message);
        return;
      }

      if (message.type === "error") {
        const messageText = message.message || "Browser transcription failed.";
        setErrorText(messageText);
        setStatusText("Transcription failed. Try a smaller model or shorter file.");
        setIsSubmitting(false);

        setRecentItems((previous) =>
          previous.map((item) =>
            item.id === activeRequest.id
              ? {
                  ...item,
                  status: "failed",
                  updatedAt: Date.now()
                }
              : item
          )
        );

        activeRequestRef.current = null;
        return;
      }

      const segments = normalizeChunkSegments(message.chunks);
      const text = typeof message.text === "string" ? message.text.trim() : "";
      const safeText = text || segments.map((segment) => segment.text).join(" ").trim();

      const durationSeconds = segments.length > 0 ? segments[segments.length - 1]?.end ?? null : null;

      const completedResult: TranscriptionResult = {
        text: safeText,
        segments,
        srt: segmentsToSrt(segments),
        metadata: {
          fileName: activeRequest.fileName,
          model: activeRequest.model,
          language: activeRequest.language,
          durationSeconds,
          runtime: "browser-worker"
        }
      };

      setResult(completedResult);

      setRecentItems((previous) =>
        previous.map((item) =>
          item.id === activeRequest.id
            ? {
                ...item,
                status: "completed",
                updatedAt: Date.now(),
                result: completedResult
              }
            : item
        )
      );

      setStatusText("Transcription complete. Export TXT or SRT below.");
      setErrorText(null);
      setIsSubmitting(false);
      activeRequestRef.current = null;
    };

    return () => {
      worker.terminate();
      workerRef.current = null;
      activeRequestRef.current = null;
    };
  }, []);

  const handleFileSelection = (file: File | null): void => {
    if (!file) {
      return;
    }

    setErrorText(null);
    setStatusText("File selected. Start transcription when ready.");
    setActiveFile(file);

    const draftId = `draft-${file.name}-${file.lastModified}`;
    setRecentItems((previous) => {
      const withoutExistingDraft = previous.filter((item) => item.id !== draftId);
      const next: RecentTranscription[] = [
        {
          id: draftId,
          fileName: file.name,
          status: "draft",
          updatedAt: Date.now(),
          model: selectedModel,
          language: language || null
        },
        ...withoutExistingDraft
      ];

      return next.slice(0, 8);
    });
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragActive(false);
    const droppedFile = event.dataTransfer.files.item(0);
    handleFileSelection(droppedFile);
  };

  const handleSubmit = async (): Promise<void> => {
    if (!activeFile) {
      setErrorText("Choose an audio/video file first.");
      return;
    }

    if (!workerRef.current) {
      setErrorText("Transcription worker is not available in this browser session.");
      return;
    }

    setIsSubmitting(true);
    setErrorText(null);
    setStatusText("Decoding audio in your browser...");

    const requestId =
      typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(16).slice(2)}`;

    try {
      const decodedAudio = await decodeAudioFile(activeFile);

      activeRequestRef.current = {
        id: requestId,
        fileName: activeFile.name,
        model: selectedModel,
        language: language || null
      };

      const processingEntry: RecentTranscription = {
        id: requestId,
        fileName: activeFile.name,
        status: "processing",
        updatedAt: Date.now(),
        model: selectedModel,
        language: language || null
      };

      setRecentItems((previous) => {
        const withoutDraftsForSameName = previous.filter(
          (item) => !(item.status === "draft" && item.fileName === activeFile.name)
        );

        return [processingEntry, ...withoutDraftsForSameName].slice(0, 8);
      });

      workerRef.current.postMessage(
        {
          type: "transcribe",
          requestId,
          audio: decodedAudio.samples,
          samplingRate: decodedAudio.sampleRate,
          model: selectedModel,
          language: language || undefined
        },
        [decodedAudio.samples.buffer]
      );
    } catch (error) {
      const rawMessage = error instanceof Error ? error.message : "Could not decode this file.";
      const message = /decode|audio data/i.test(rawMessage)
        ? "Your browser could not decode this file. Convert it to WAV/MP3 and try again."
        : rawMessage;
      setErrorText(message);
      setStatusText("Transcription failed before inference started.");
      setIsSubmitting(false);
      activeRequestRef.current = null;
    }
  };

  const copyTranscript = async (): Promise<void> => {
    if (!activeResult?.text || typeof navigator === "undefined" || !navigator.clipboard) {
      return;
    }

    await navigator.clipboard.writeText(activeResult.text);
    setStatusText("Transcript copied to clipboard.");
  };

  const copyTimestampedTranscript = async (): Promise<void> => {
    if (!activeResult || typeof navigator === "undefined" || !navigator.clipboard) {
      return;
    }

    const segments = activeResult.segments.length
      ? activeResult.segments
      : [{ start: 0, end: 0, text: activeResult.text }];

    await navigator.clipboard.writeText(buildTimestampedTranscript(segments));
    setStatusText("Timestamped transcript copied to clipboard.");
  };

  return (
    <section className="transcriptionStudio" aria-label="Transcription workspace">
      <section className="uploadSection" aria-label="Upload audio/video">
        <div
          className={`uploadCard ${isDragActive ? "uploadCardActive" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragActive(true);
          }}
          onDragLeave={() => setIsDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              fileInputRef.current?.click();
            }
          }}
        >
          <div className="uploadIllustration" aria-hidden="true">
            <span />
            <span />
            <span />
            <span />
            <span />
            <span />
          </div>

          <h2 className="uploadTitle">Drag &amp; drop your audio or video file here.</h2>
          <p className="uploadMeta">Supports MP3, WAV, MP4, MOV, M4A, OGG, AAC, WEBM.</p>

          <button
            type="button"
            className="primaryButton"
            onClick={(event) => {
              event.stopPropagation();
              fileInputRef.current?.click();
            }}
          >
            Browse Files
          </button>

          <input
            ref={fileInputRef}
            hidden
            type="file"
            accept="audio/*,video/*"
            onChange={(event) => handleFileSelection(event.target.files?.item(0) ?? null)}
          />
        </div>
      </section>

      <section className="controlSection" aria-label="Transcription controls">
        <div className="controlGrid">
          <div className="fieldGroup">
            <label htmlFor="model-select">Whisper Model</label>
            <select
              id="model-select"
              value={selectedModel}
              onChange={(event) => setSelectedModel(event.target.value)}
              disabled={isSubmitting}
            >
              {modelOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="fieldGroup">
            <label htmlFor="language-select">Language</label>
            <select
              id="language-select"
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
              disabled={isSubmitting}
            >
              {languageOptions.map((option) => (
                <option key={option.value || "auto"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="controlActions">
          <button type="button" className="primaryButton" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Transcribing..." : "Start Local Transcription"}
          </button>
          <button
            type="button"
            className="ghostButton"
            onClick={() => {
              activeRequestRef.current = null;
              setActiveFile(null);
              setResult(null);
              setLanguage("");
              setSelectedModel(modelOptions[0].value);
              setErrorText(null);
              setStatusText("Workspace reset.");
            }}
            disabled={isSubmitting}
          >
            Reset
          </button>
        </div>

        <p className="selectedFileLine">{fileSizeLabel}</p>
        <p className={`statusLine ${errorText ? "statusLineError" : ""}`}>{errorText ?? statusText}</p>
      </section>

      <section className="recentSection" aria-label="Recent transcriptions">
        <h3 className="sectionTitle">Recent Transcriptions</h3>
        <div className="recentList">
          {renderedRecentItems.map((item) => (
            <article key={item.id} className="recentCard">
              <div className={`statusIcon status-${item.status}`} aria-hidden="true">
                {item.status === "processing" ? (
                  <div className="dotCluster">
                    <span className="dotPulse" />
                    <span className="dotPulse" />
                    <span className="dotPulse" />
                  </div>
                ) : item.status === "completed" ? (
                  <svg viewBox="0 0 20 20" fill="currentColor" role="img" aria-label="Completed">
                    <path
                      fillRule="evenodd"
                      clipRule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    />
                  </svg>
                ) : item.status === "failed" ? (
                  <svg viewBox="0 0 20 20" fill="currentColor" role="img" aria-label="Failed">
                    <path
                      fillRule="evenodd"
                      clipRule="evenodd"
                      d="M18 10A8 8 0 112 10a8 8 0 0116 0zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                    />
                  </svg>
                ) : (
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" role="img" aria-label="Draft">
                    <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                )}
              </div>

              <div className="recentContent">
                <p className="recentFileName">{item.fileName}</p>
                <p className="recentMeta">{getStatusLine(item)}</p>
              </div>

              <button
                type="button"
                className="inlineLinkButton"
                onClick={() => {
                  if (item.result) {
                    setResult(item.result);
                    setStatusText(`Loaded transcript: ${item.fileName}`);
                  }
                }}
                disabled={!item.result}
              >
                View
              </button>
            </article>
          ))}
        </div>
      </section>

      <section className="outputSection" aria-label="Transcript output">
        <div className="outputHeader">
          <h3 className="sectionTitle">Transcript Output</h3>
          <div className="metaStrip">
            <span className="pill">Mode: Browser Worker</span>
            <span className="pill">Export: TXT + SRT</span>
          </div>
        </div>

        {!activeResult ? (
          <div className="emptyOutput">
            Run a transcription to view timestamped segments and export actions here.
          </div>
        ) : (
          <>
            <div className="controlActions compactActions">
              <button
                type="button"
                className="ghostButton"
                onClick={() =>
                  downloadTextFile(
                    `${activeResult.metadata.fileName.replace(/\.[^.]+$/, "") || "transcript"}.txt`,
                    `${activeResult.text.trim()}\n`
                  )
                }
              >
                Download TXT
              </button>
              <button
                type="button"
                className="ghostButton"
                onClick={() =>
                  downloadTextFile(
                    `${activeResult.metadata.fileName.replace(/\.[^.]+$/, "") || "transcript"}.srt`,
                    activeResult.srt || ""
                  )
                }
                disabled={!activeResult.srt}
              >
                Download SRT
              </button>
              <button type="button" className="ghostButton" onClick={copyTranscript}>
                Copy Text
              </button>
              <button type="button" className="ghostButton" onClick={copyTimestampedTranscript}>
                Copy with Timestamps
              </button>
            </div>

            <div className="metaStrip outputMetaStrip">
              <span className="pill">File: {activeResult.metadata.fileName}</span>
              <span className="pill">Model: {activeResult.metadata.model}</span>
              {activeResult.metadata.language ? <span className="pill">Language: {activeResult.metadata.language}</span> : null}
              {typeof activeResult.metadata.durationSeconds === "number" ? (
                <span className="pill">Duration: {formatClockTime(activeResult.metadata.durationSeconds)}</span>
              ) : null}
            </div>

            <ul className="segmentList" aria-label="Timestamped transcript segments">
              {(activeResult.segments.length
                ? activeResult.segments
                : [{ start: 0, end: 0, text: activeResult.text }]
              ).map((segment, index) => (
                <li key={`${segment.start}-${segment.end}-${index}`} className="segmentItem">
                  <span className="segmentTime">
                    {formatClockTime(segment.start)} - {formatClockTime(segment.end)}
                  </span>
                  <p className="segmentText">{segment.text}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    </section>
  );
}
