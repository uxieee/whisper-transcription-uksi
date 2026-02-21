import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";
import { NextResponse } from "next/server";
import { z } from "zod";
import { normalizeSegments, segmentsToSrt } from "@/lib/transcript";

const MAX_UPLOAD_MB = (() => {
  const value = Number.parseInt(process.env.MAX_UPLOAD_MB ?? "64", 10);
  return Number.isFinite(value) ? Math.min(256, Math.max(1, value)) : 64;
})();

const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024;
const LOCAL_SCRIPT_PATH = path.join(process.cwd(), "scripts", "local_transcribe.py");
const LOCAL_MODEL = process.env.LOCAL_WHISPER_MODEL?.trim() || "turbo";
const LOCAL_DEVICE = process.env.LOCAL_WHISPER_DEVICE?.trim() || "cpu";
const LOCAL_TIMEOUT_MS = (() => {
  const value = Number.parseInt(process.env.LOCAL_TRANSCRIBE_TIMEOUT_MS ?? "900000", 10);
  return Number.isFinite(value) ? Math.min(3_600_000, Math.max(30_000, value)) : 900_000;
})();

const allowedMimeTypes = new Set([
  "audio/mpeg",
  "audio/mp3",
  "audio/wav",
  "audio/x-wav",
  "audio/mp4",
  "audio/m4a",
  "audio/aac",
  "audio/ogg",
  "audio/webm",
  "video/mp4"
]);

const allowedExtensions = new Set(["mp3", "wav", "m4a", "mp4", "ogg", "aac", "webm"]);

const fieldSchema = z.object({
  language: z
    .string()
    .trim()
    .max(8)
    .regex(/^[a-z]{2,3}$/i, "Language must be an ISO code like en or tl")
    .optional(),
  prompt: z.string().trim().max(240).optional()
});

const localOutputSchema = z.object({
  text: z.string().optional(),
  segments: z
    .array(
      z.object({
        start: z.number(),
        end: z.number(),
        text: z.string()
      })
    )
    .optional(),
  duration: z.number().nullable().optional(),
  error: z.string().optional()
});

export const runtime = "nodejs";
export const maxDuration = 300;

function extensionAllowed(fileName: string): boolean {
  const extension = fileName.split(".").pop()?.toLowerCase();
  return extension ? allowedExtensions.has(extension) : false;
}

function safeSuffix(fileName: string): string {
  const ext = path.extname(fileName).toLowerCase();
  if (!ext) {
    return ".bin";
  }

  const sanitized = ext.replace(/[^.a-z0-9]/g, "");
  return sanitized.length > 1 && sanitized.length <= 10 ? sanitized : ".bin";
}

function truncateMessage(message: string): string {
  const cleaned = message.replace(/\s+/g, " ").trim();
  if (!cleaned) {
    return "Local transcription failed.";
  }

  return cleaned.length > 220 ? `${cleaned.slice(0, 217)}...` : cleaned;
}

type ProcessResult = {
  stdout: string;
  stderr: string;
  exitCode: number | null;
  timedOut: boolean;
  spawnError: string | null;
};

function runProcess(command: string, args: string[], timeoutMs: number): Promise<ProcessResult> {
  return new Promise((resolve) => {
    let stdout = "";
    let stderr = "";
    let timedOut = false;
    let spawnError: string | null = null;

    const child = spawn(command, args, {
      cwd: process.cwd(),
      env: process.env,
      stdio: ["ignore", "pipe", "pipe"]
    });

    const timeout = setTimeout(() => {
      timedOut = true;
      child.kill("SIGKILL");
    }, timeoutMs);

    child.stdout.on("data", (chunk: Buffer) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk: Buffer) => {
      stderr += chunk.toString();
    });

    child.on("error", (error) => {
      spawnError = error.message;
    });

    child.on("close", (exitCode) => {
      clearTimeout(timeout);
      resolve({
        stdout,
        stderr,
        exitCode,
        timedOut,
        spawnError
      });
    });
  });
}

function parseLocalOutput(stdout: string): z.infer<typeof localOutputSchema> | null {
  const lines = stdout
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  for (let index = lines.length - 1; index >= 0; index -= 1) {
    try {
      const parsed = JSON.parse(lines[index]);
      const validated = localOutputSchema.safeParse(parsed);
      if (validated.success) {
        return validated.data;
      }
    } catch {
      // Ignore non-JSON lines and continue searching from bottom.
    }
  }

  return null;
}

async function resolvePythonCandidates(): Promise<string[]> {
  const fromEnv = process.env.LOCAL_PYTHON_BIN?.trim();
  const candidates = [fromEnv, "python3", "python"].filter(
    (value): value is string => Boolean(value)
  );

  const uniqueCandidates = Array.from(new Set(candidates));

  const validated = await Promise.all(
    uniqueCandidates.map(async (candidate) => {
      if (candidate === "python3" || candidate === "python") {
        return candidate;
      }

      try {
        await fs.access(candidate);
        return candidate;
      } catch {
        return null;
      }
    })
  );

  return validated.filter((candidate): candidate is string => Boolean(candidate));
}

export async function POST(request: Request): Promise<Response> {
  try {
    await fs.access(LOCAL_SCRIPT_PATH);
  } catch {
    return NextResponse.json(
      {
        error: {
          code: "LOCAL_SCRIPT_MISSING",
          message: "Local transcription script not found at scripts/local_transcribe.py."
        }
      },
      { status: 500 }
    );
  }

  const formData = await request.formData();
  const fileCandidate = formData.get("file");

  if (!(fileCandidate instanceof File)) {
    return NextResponse.json(
      { error: { code: "INVALID_FILE", message: "Attach one audio file to transcribe." } },
      { status: 400 }
    );
  }

  if (fileCandidate.size === 0 || fileCandidate.size > MAX_UPLOAD_BYTES) {
    return NextResponse.json(
      {
        error: {
          code: "INVALID_SIZE",
          message: `File size must be between 1 byte and ${MAX_UPLOAD_MB}MB.`
        }
      },
      { status: 413 }
    );
  }

  if (!allowedMimeTypes.has(fileCandidate.type) && !extensionAllowed(fileCandidate.name)) {
    return NextResponse.json(
      {
        error: {
          code: "INVALID_TYPE",
          message: "Supported formats: mp3, wav, m4a, mp4, ogg, aac, webm."
        }
      },
      { status: 415 }
    );
  }

  const payloadValidation = fieldSchema.safeParse({
    language: (() => {
      const value = formData.get("language");
      return typeof value === "string" && value.length > 0 ? value : undefined;
    })(),
    prompt: (() => {
      const value = formData.get("prompt");
      return typeof value === "string" && value.length > 0 ? value : undefined;
    })()
  });

  if (!payloadValidation.success) {
    return NextResponse.json(
      {
        error: {
          code: "INVALID_INPUT",
          message: payloadValidation.error.issues[0]?.message ?? "Invalid request body."
        }
      },
      { status: 422 }
    );
  }

  const pythonCandidates = await resolvePythonCandidates();
  if (!pythonCandidates.length) {
    return NextResponse.json(
      {
        error: {
          code: "PYTHON_NOT_FOUND",
          message: "No Python runtime found. Install python3 or set LOCAL_PYTHON_BIN."
        }
      },
      { status: 500 }
    );
  }

  const tempDir = await fs.mkdtemp(path.join(os.tmpdir(), "whisper-web-"));
  const tempInputPath = path.join(tempDir, `input${safeSuffix(fileCandidate.name)}`);

  try {
    const fileBuffer = Buffer.from(await fileCandidate.arrayBuffer());
    await fs.writeFile(tempInputPath, fileBuffer);

    const scriptArgs = [
      LOCAL_SCRIPT_PATH,
      "--input",
      tempInputPath,
      "--model",
      LOCAL_MODEL,
      "--device",
      LOCAL_DEVICE
    ];

    if (payloadValidation.data.language) {
      scriptArgs.push("--language", payloadValidation.data.language);
    }

    if (payloadValidation.data.prompt) {
      scriptArgs.push("--prompt", payloadValidation.data.prompt);
    }

    let lastFailure = "";

    for (const candidate of pythonCandidates) {
      const result = await runProcess(candidate, scriptArgs, LOCAL_TIMEOUT_MS);

      if (result.timedOut) {
        lastFailure = `Transcription timed out after ${Math.round(LOCAL_TIMEOUT_MS / 1000)} seconds.`;
        continue;
      }

      if (result.spawnError) {
        if (!/ENOENT/i.test(result.spawnError)) {
          lastFailure = result.spawnError;
        }
        continue;
      }

      if (result.exitCode !== 0) {
        const parsedFailure = parseLocalOutput(result.stdout);
        if (parsedFailure?.error) {
          lastFailure = parsedFailure.error;
        } else {
          lastFailure = result.stderr || result.stdout || `Python exited with code ${result.exitCode}.`;
        }
        continue;
      }

      const parsed = parseLocalOutput(result.stdout);
      if (!parsed) {
        lastFailure = "Could not parse local transcription output.";
        continue;
      }

      if (parsed.error) {
        lastFailure = parsed.error;
        continue;
      }

      const segments = normalizeSegments(parsed.segments ?? []);
      const safeText = (parsed.text ?? "").trim() || segments.map((segment) => segment.text).join(" ").trim();

      return NextResponse.json({
        data: {
          text: safeText,
          segments,
          srt: segmentsToSrt(segments),
          metadata: {
            fileName: fileCandidate.name,
            model: LOCAL_MODEL,
            language: payloadValidation.data.language ?? null,
            durationSeconds: typeof parsed.duration === "number" ? parsed.duration : null,
            runtime: "local-python"
          }
        }
      });
    }

    return NextResponse.json(
      {
        error: {
          code: "TRANSCRIPTION_FAILED",
          message: truncateMessage(lastFailure || "No working Python runtime was available for transcription.")
        }
      },
      { status: 500 }
    );
  } finally {
    await fs.rm(tempDir, { recursive: true, force: true });
  }
}
