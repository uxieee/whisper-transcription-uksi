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

const languageOptions = [
  { value: "", label: "Auto detect" },
  { value: "en", label: "English" },
  { value: "tl", label: "Tagalog" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" }
];

const modelOptions = [
  { value: "Xenova/whisper-tiny", label: "Whisper Tiny (fastest)" },
  { value: "Xenova/whisper-base", label: "Whisper Base (balanced)" },
  { value: "Xenova/whisper-small", label: "Whisper Small (best quality)" }
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
  if (typeof window === "undefined" || typeof window.AudioContext === "undefined") {
    throw new Error("This browser does not support AudioContext decoding.");
  }

  const context = new window.AudioContext();

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
    "Drop an audio file or choose one. Transcription runs in your browser, not on a server."
  );
  const [errorText, setErrorText] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptionResult | null>(null);

  const activeResult = result;

  const fileSizeLabel = useMemo(() => {
    if (!activeFile) {
      return "No file selected";
    }

    return `${activeFile.name} • ${(activeFile.size / 1024 / 1024).toFixed(2)} MB`;
  }, [activeFile]);

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
        setErrorText(message.message || "Browser transcription failed.");
        setStatusText("Transcription failed. Try a smaller model or shorter file.");
        setIsSubmitting(false);
        activeRequestRef.current = null;
        return;
      }

      const segments = normalizeChunkSegments(message.chunks);
      const text = typeof message.text === "string" ? message.text.trim() : "";
      const safeText = text || segments.map((segment) => segment.text).join(" ").trim();

      const durationSeconds =
        segments.length > 0
          ? segments[segments.length - 1]?.end ?? null
          : null;

      setResult({
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
      });

      setStatusText("Transcription complete. You can export TXT or SRT now.");
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
    setStatusText("File ready. Start transcription to begin local model loading.");
    setActiveFile(file);
  };

  const handleDrop = (event: React.DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setIsDragActive(false);
    const droppedFile = event.dataTransfer.files.item(0);
    handleFileSelection(droppedFile);
  };

  const handleSubmit = async (): Promise<void> => {
    if (!activeFile) {
      setErrorText("Choose an audio file first.");
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
      const message = error instanceof Error ? error.message : "Could not decode this audio file.";
      setErrorText(message);
      setStatusText("Transcription failed before inference started.");
      setIsSubmitting(false);
      activeRequestRef.current = null;
    }
  };

  const copyTranscript = async (): Promise<void> => {
    if (!activeResult?.text) {
      return;
    }

    await navigator.clipboard.writeText(activeResult.text);
    setStatusText("Transcript copied to clipboard.");
  };

  return (
    <section className="studioGrid" aria-label="Transcription workspace">
      <article className="panel formPanel" aria-labelledby="input-title">
        <h2 id="input-title" className="panelTitle">
          Input & Controls
        </h2>
        <p className="panelSubcopy">
          Browser-local mode. First run downloads model files, then transcription stays on-device.
        </p>

        <div
          className={`dropzone ${isDragActive ? "dropzoneActive" : ""}`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragActive(true);
          }}
          onDragLeave={() => setIsDragActive(false)}
          onDrop={handleDrop}
        >
          <strong>Drop audio here</strong>
          <div className="dropzoneMeta">or use the file button below • mp3/wav/m4a/mp4/ogg/aac/webm</div>
        </div>

        <div className="buttonRow">
          <button
            type="button"
            className="fileButton"
            onClick={() => {
              fileInputRef.current?.click();
            }}
          >
            Choose Audio File
          </button>
          <input
            ref={fileInputRef}
            hidden
            type="file"
            accept="audio/*,video/mp4"
            onChange={(event) => handleFileSelection(event.target.files?.item(0) ?? null)}
          />
        </div>

        <p className="inlineInfo">{fileSizeLabel}</p>

        <div className="inputRow">
          <div className="field">
            <label htmlFor="model-select">Model</label>
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

          <div className="field">
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

        <div className="buttonRow">
          <button type="button" className="btn btnPrimary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Transcribing..." : "Start Local Transcription"}
          </button>
          <button
            type="button"
            className="btn btnGhost"
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

        <p className={`inlineInfo ${errorText ? "inlineInfoError" : ""}`}>{errorText ?? statusText}</p>
      </article>

      <article className="panel resultPanel" aria-labelledby="result-title">
        <div className="outputHeader">
          <h2 id="result-title" className="panelTitle">
            Transcript Output
          </h2>
          <div className="metaStrip">
            <span className="badge">Model: {activeResult?.metadata.model ?? "whisper-browser"}</span>
            <span className="badge">Format: TXT + SRT</span>
            <span className="badge">Mode: Browser Local</span>
          </div>
        </div>

        {!activeResult ? (
          <div className="emptyState">
            Your transcript will appear here with timestamped segments and export actions.
          </div>
        ) : (
          <>
            <div className="buttonRow">
              <button
                type="button"
                className="btn btnGhost"
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
                className="btn btnGhost"
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
              <button type="button" className="btn btnGhost" onClick={copyTranscript}>
                Copy Text
              </button>
            </div>

            <div className="metaStrip">
              <span className="badge">File: {activeResult.metadata.fileName}</span>
              {activeResult.metadata.language ? (
                <span className="badge">Language: {activeResult.metadata.language}</span>
              ) : null}
              {typeof activeResult.metadata.durationSeconds === "number" ? (
                <span className="badge">Duration: {formatClockTime(activeResult.metadata.durationSeconds)}</span>
              ) : null}
            </div>

            <ul className="segmentList" aria-label="Timestamped transcript segments">
              {(
                activeResult.segments.length
                  ? activeResult.segments
                  : [{ start: 0, end: 0, text: activeResult.text }]
              ).map((segment, index) => (
                <li key={`${segment.start}-${segment.end}-${index}`} className="segment">
                  <span className="segmentTime">
                    {formatClockTime(segment.start)} - {formatClockTime(segment.end)}
                  </span>
                  <p className="segmentText">{segment.text}</p>
                </li>
              ))}
            </ul>
          </>
        )}
      </article>
    </section>
  );
}
