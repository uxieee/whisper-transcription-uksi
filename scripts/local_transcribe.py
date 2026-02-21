#!/usr/bin/env python3
"""Local Whisper bridge for the web app API route.

Runs transcription with the existing local pipeline and prints JSON for Node to parse.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from transcribe import transcribe_audio


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Whisper transcription and return JSON.")
    parser.add_argument("--input", required=True, help="Path to input audio file")
    parser.add_argument("--model", default="turbo", help="Whisper model size")
    parser.add_argument("--language", default="", help="ISO language code (blank for auto)")
    parser.add_argument("--prompt", default="", help="Initial prompt/context")
    parser.add_argument("--device", default="cpu", help="Execution device: cpu/cuda/mps")
    return parser.parse_args()


def normalize_segments(raw_segments: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_segments, list):
        return []

    normalized: list[dict[str, Any]] = []
    for segment in raw_segments:
        if not isinstance(segment, dict):
            continue

        try:
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
        except (TypeError, ValueError):
            continue

        text = str(segment.get("text", "")).strip()
        if not text:
            continue

        normalized.append(
            {
                "start": max(0.0, start),
                "end": max(start, end),
                "text": text,
            }
        )

    return normalized


def main() -> int:
    args = parse_args()

    language = args.language.strip().lower() or None
    prompt = args.prompt.strip() or None

    try:
        result = transcribe_audio(
            audio_path=args.input,
            model_size=args.model,
            prompt=prompt,
            language=language,
            device=args.device,
            verbose=False,
        )
    except Exception as exc:  # pragma: no cover
        print(json.dumps({"error": f"Local transcription failed: {exc}"}, ensure_ascii=False))
        return 1

    if not result:
        print(json.dumps({"error": "Local transcription returned no result."}, ensure_ascii=False))
        return 1

    payload = {
        "text": str(result.get("text", "")).strip(),
        "segments": normalize_segments(result.get("segments", [])),
        "duration": result.get("duration"),
    }

    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
