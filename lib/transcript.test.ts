import { describe, expect, it } from "vitest";
import { formatClockTime, formatSrtTimestamp, normalizeSegments, segmentsToSrt } from "./transcript";

describe("transcript utilities", () => {
  it("formats SRT timestamp with millisecond precision", () => {
    expect(formatSrtTimestamp(0)).toBe("00:00:00,000");
    expect(formatSrtTimestamp(61.234)).toBe("00:01:01,234");
    expect(formatSrtTimestamp(59.9995)).toBe("00:01:00,000");
  });

  it("normalizes valid segments only", () => {
    const normalized = normalizeSegments([
      { start: 0, end: 2, text: "Hello" },
      { start: 2.1, end: 3.4, text: "World" },
      { start: "bad", end: 3.4, text: "No" }
    ]);

    expect(normalized).toHaveLength(2);
    expect(normalized[0]?.text).toBe("Hello");
  });

  it("builds SRT blocks", () => {
    const srt = segmentsToSrt([
      { start: 0, end: 1.4, text: "Alpha" },
      { start: 1.4, end: 3.0, text: "Beta" }
    ]);

    expect(srt).toContain("1");
    expect(srt).toContain("00:00:00,000 --> 00:00:01,400");
    expect(srt).toContain("Beta");
  });

  it("formats clock values for UI badges", () => {
    expect(formatClockTime(65)).toBe("01:05");
    expect(formatClockTime(3665)).toBe("01:01:05");
  });
});
