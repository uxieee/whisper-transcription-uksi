/// <reference lib="webworker" />

type WhisperRequest = {
  type: "transcribe";
  requestId: string;
  audio: Float32Array;
  samplingRate: number;
  model: string;
  language?: string;
};

type WhisperChunk = {
  text: string;
  timestamp?: [number | null, number | null] | null;
};

type WhisperOutput = {
  text?: string;
  chunks?: WhisperChunk[];
};

let currentModel: string | null = null;
type AsrCallable = (audio: unknown, options: Record<string, unknown>) => Promise<WhisperOutput>;
let transcriberPromise: Promise<AsrCallable> | null = null;
let transformersRuntimeConfigured = false;

function toFloat32Audio(input: unknown): Float32Array {
  if (input instanceof Float32Array) {
    return input;
  }

  if (Array.isArray(input)) {
    return Float32Array.from(input);
  }

  if (ArrayBuffer.isView(input)) {
    const view = input as ArrayBufferView;
    return new Float32Array(view.buffer, view.byteOffset, Math.floor(view.byteLength / Float32Array.BYTES_PER_ELEMENT));
  }

  if (input instanceof ArrayBuffer) {
    return new Float32Array(input);
  }

  if (input && typeof input === "object") {
    const candidate = input as { array?: unknown };
    if (candidate.array !== undefined) {
      return toFloat32Audio(candidate.array);
    }
  }

  throw new Error("Invalid audio payload. Expected Float32Array audio samples.");
}

function postStatus(requestId: string, message: string, stage: "loading" | "running" | "ready"): void {
  self.postMessage({ type: "status", requestId, stage, message });
}

function parseProgress(value: unknown): number | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const candidate = value as { progress?: unknown };
  if (typeof candidate.progress !== "number") {
    return null;
  }

  if (candidate.progress > 1) {
    return Math.min(100, Math.max(0, candidate.progress));
  }

  return Math.min(100, Math.max(0, candidate.progress * 100));
}

async function getTranscriber(model: string, requestId: string) {
  if (!transcriberPromise || currentModel !== model) {
    currentModel = model;
    postStatus(requestId, `Loading ${model} in your browser (first run downloads model files).`, "loading");

    const { env, pipeline } = await import("@huggingface/transformers");

    if (!transformersRuntimeConfigured) {
      env.allowLocalModels = false;
      if (env.backends?.onnx?.wasm) {
        // Threaded WASM can fail on some mobile/low-memory browsers.
        env.backends.onnx.wasm.numThreads = 1;
        env.backends.onnx.wasm.proxy = false;
      }
      transformersRuntimeConfigured = true;
    }

    transcriberPromise = pipeline("automatic-speech-recognition", model, {
      progress_callback: (progressInfo: unknown) => {
        const progress = parseProgress(progressInfo);
        if (progress === null) {
          return;
        }

        self.postMessage({
          type: "status",
          requestId,
          stage: "loading",
          message: `Downloading model assets: ${progress.toFixed(0)}%`
        });
      }
    }) as unknown as Promise<AsrCallable>;

    await transcriberPromise;
    postStatus(requestId, `${model} is ready locally.`, "ready");
  }

  return transcriberPromise;
}

self.addEventListener("message", async (event: MessageEvent<WhisperRequest>) => {
  if (event.data?.type !== "transcribe") {
    return;
  }

  const { requestId, audio, samplingRate, model, language } = event.data;

  try {
    const transcriber = await getTranscriber(model, requestId);
    const normalizedAudio = toFloat32Audio(audio);

    postStatus(requestId, "Running local transcription in browser...", "running");

    const output = await transcriber(normalizedAudio, {
      sampling_rate: samplingRate,
      task: "transcribe",
      language: language || undefined,
      chunk_length_s: 30,
      stride_length_s: 5,
      return_timestamps: true
    });

    self.postMessage({
      type: "complete",
      requestId,
      text: output?.text ?? "",
      chunks: Array.isArray(output?.chunks) ? output.chunks : []
    });
  } catch (error) {
    const message =
      error instanceof Error
        ? `${error.name}: ${error.message}`
        : typeof error === "string"
          ? error
          : (() => {
              try {
                return `Browser transcription failed: ${JSON.stringify(error)}`;
              } catch {
                return "Browser transcription failed.";
              }
            })();
    self.postMessage({ type: "error", requestId, message });
  }
});

export {};
