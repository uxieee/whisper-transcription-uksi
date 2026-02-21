export type TranscriptSegment = {
  start: number;
  end: number;
  text: string;
  speaker?: string;
};

function sanitizeTimestampValue(seconds: number): number {
  if (!Number.isFinite(seconds)) {
    return 0;
  }

  return Math.max(0, seconds);
}

export function formatSrtTimestamp(seconds: number): string {
  const totalMs = Math.round(sanitizeTimestampValue(seconds) * 1000);
  const hours = Math.floor(totalMs / 3_600_000);
  const minutes = Math.floor((totalMs % 3_600_000) / 60_000);
  const secs = Math.floor((totalMs % 60_000) / 1_000);
  const millis = totalMs % 1_000;

  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(
    secs
  ).padStart(2, "0")},${String(millis).padStart(3, "0")}`;
}

export function formatClockTime(seconds: number): string {
  const totalSeconds = Math.floor(sanitizeTimestampValue(seconds));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }

  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

export function normalizeSegments(rawSegments: unknown): TranscriptSegment[] {
  if (!Array.isArray(rawSegments)) {
    return [];
  }

  const normalized = rawSegments
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const candidate = item as {
        start?: unknown;
        end?: unknown;
        text?: unknown;
      };

      const start = Number(candidate.start);
      const end = Number(candidate.end);
      const text = typeof candidate.text === "string" ? candidate.text.trim() : "";

      if (!Number.isFinite(start) || !Number.isFinite(end) || !text) {
        return null;
      }

      return {
        start: Math.max(0, start),
        end: Math.max(start, end),
        text
      } satisfies TranscriptSegment;
    })
    .filter((segment): segment is TranscriptSegment => Boolean(segment));

  return normalized;
}

export function segmentsToSrt(segments: TranscriptSegment[]): string {
  if (!segments.length) {
    return "";
  }

  return segments
    .map((segment, index) => {
      const start = formatSrtTimestamp(segment.start);
      const end = formatSrtTimestamp(segment.end);
      return `${index + 1}\n${start} --> ${end}\n${segment.text.trim()}\n`;
    })
    .join("\n");
}
