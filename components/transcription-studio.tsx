"use client";

import { useMemo, useRef, useState } from "react";
import { formatClockTime, type TranscriptSegment } from "@/lib/transcript";

type TranscriptionResponse = {
  data: {
    text: string;
    srt: string;
    segments: TranscriptSegment[];
    metadata: {
      fileName: string;
      model: string;
      language: string | null;
      durationSeconds: number | null;
    };
  };
};

type ApiErrorResponse = {
  error?: {
    message?: string;
  };
};

const languageOptions = [
  { value: "", label: "Auto detect" },
  { value: "en", label: "English" },
  { value: "tl", label: "Tagalog" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" }
];

const MAX_UPLOAD_MB = 4;

function downloadTextFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function TranscriptionStudio() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [activeFile, setActiveFile] = useState<File | null>(null);
  const [language, setLanguage] = useState("");
  const [prompt, setPrompt] = useState("");
  const [isDragActive, setIsDragActive] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusText, setStatusText] = useState("Drop an audio file or choose one to begin.");
  const [errorText, setErrorText] = useState<string | null>(null);
  const [result, setResult] = useState<TranscriptionResponse["data"] | null>(null);

  const activeResult = result;

  const fileSizeLabel = useMemo(() => {
    if (!activeFile) {
      return "No file selected";
    }

    return `${activeFile.name} • ${(activeFile.size / 1024 / 1024).toFixed(2)} MB`;
  }, [activeFile]);

  const handleFileSelection = (file: File | null): void => {
    if (!file) {
      return;
    }

    if (file.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setErrorText(`File too large. The current hosted limit is ${MAX_UPLOAD_MB}MB.`);
      return;
    }

    setErrorText(null);
    setStatusText("File ready. Set options and start transcription.");
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

    setIsSubmitting(true);
    setErrorText(null);
    setStatusText("Uploading audio and running Whisper transcription...");

    const formData = new FormData();
    formData.append("file", activeFile);
    if (language) {
      formData.append("language", language);
    }
    if (prompt.trim()) {
      formData.append("prompt", prompt.trim());
    }

    try {
      const response = await fetch("/api/transcriptions", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        const errorPayload = (await response.json()) as ApiErrorResponse;
        throw new Error(errorPayload.error?.message ?? "Transcription request failed.");
      }

      const payload = (await response.json()) as TranscriptionResponse;
      setResult(payload.data);
      setStatusText("Transcription complete. You can export TXT or SRT now.");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown error";
      setErrorText(message);
      setStatusText("Transcription failed. Adjust file/settings and retry.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const copyTranscript = async (): Promise<void> => {
    if (!result?.text) {
      return;
    }

    await navigator.clipboard.writeText(result.text);
    setStatusText("Transcript copied to clipboard.");
  };

  return (
    <section className="studioGrid" aria-label="Transcription workspace">
      <article className="panel formPanel" aria-labelledby="input-title">
        <h2 id="input-title" className="panelTitle">
          Input & Controls
        </h2>
        <p className="panelSubcopy">Upload one file up to 4MB (optimized for Vercel hosted uploads).</p>

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
            <label htmlFor="language-select">Language</label>
            <select
              id="language-select"
              value={language}
              onChange={(event) => setLanguage(event.target.value)}
            >
              {languageOptions.map((option) => (
                <option key={option.value || "auto"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <label htmlFor="prompt-input">Initial Prompt (Optional)</label>
            <textarea
              id="prompt-input"
              placeholder="Example: Conversation is mostly Tagalog with some English terminology."
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              maxLength={240}
            />
          </div>
        </div>

        <div className="buttonRow">
          <button type="button" className="btn btnPrimary" onClick={handleSubmit} disabled={isSubmitting}>
            {isSubmitting ? "Transcribing..." : "Start Transcription"}
          </button>
          <button
            type="button"
            className="btn btnGhost"
            onClick={() => {
              setActiveFile(null);
              setResult(null);
              setPrompt("");
              setLanguage("");
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
            <span className="badge">Model: whisper-1</span>
            <span className="badge">Format: TXT + SRT</span>
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
