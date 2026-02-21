import OpenAI from "openai";
import { NextResponse } from "next/server";
import { z } from "zod";
import { normalizeSegments, segmentsToSrt } from "@/lib/transcript";

const MAX_UPLOAD_BYTES = 4 * 1024 * 1024;
const TRANSCRIPTION_MODEL = "whisper-1";

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

export const runtime = "nodejs";
export const maxDuration = 60;

function extensionAllowed(fileName: string): boolean {
  const extension = fileName.split(".").pop()?.toLowerCase();
  return extension ? allowedExtensions.has(extension) : false;
}

function sanitizeErrorMessage(message: string | null | undefined): string {
  if (!message) {
    return "Transcription failed.";
  }

  if (message.length > 180) {
    return "Transcription failed due to an upstream processing error.";
  }

  return message;
}

export async function POST(request: Request): Promise<Response> {
  if (!process.env.OPENAI_API_KEY) {
    return NextResponse.json(
      {
        error: {
          code: "OPENAI_KEY_MISSING",
          message: "Server is not configured with OPENAI_API_KEY."
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
          message: `File size must be between 1 byte and ${Math.floor(MAX_UPLOAD_BYTES / 1024 / 1024)}MB.`
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

  try {
    const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
    const transcription = await openai.audio.transcriptions.create({
      file: fileCandidate,
      model: TRANSCRIPTION_MODEL,
      response_format: "verbose_json",
      language: payloadValidation.data.language,
      prompt: payloadValidation.data.prompt,
      temperature: 0
    });

    const text = typeof transcription.text === "string" ? transcription.text.trim() : "";
    const segments = normalizeSegments((transcription as { segments?: unknown }).segments);
    const safeText = text || segments.map((segment) => segment.text).join(" ").trim();

    return NextResponse.json({
      data: {
        text: safeText,
        segments,
        srt: segmentsToSrt(segments),
        metadata: {
          fileName: fileCandidate.name,
          model: TRANSCRIPTION_MODEL,
          language: payloadValidation.data.language ?? null,
          durationSeconds:
            typeof (transcription as { duration?: unknown }).duration === "number"
              ? (transcription as { duration: number }).duration
              : null
        }
      }
    });
  } catch (error) {
    const fallback = "We could not transcribe this file right now. Try again in a moment.";

    if (error instanceof OpenAI.APIError) {
      return NextResponse.json(
        {
          error: {
            code: `OPENAI_${error.status ?? 500}`,
            message: sanitizeErrorMessage(error.message) || fallback
          }
        },
        { status: error.status ?? 502 }
      );
    }

    return NextResponse.json(
      {
        error: {
          code: "TRANSCRIPTION_FAILED",
          message: fallback
        }
      },
      { status: 500 }
    );
  }
}
