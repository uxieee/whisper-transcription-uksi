# Whisper Transcription Uksi Web App Design

## Goal

Provide a browser-based interface for the existing local Whisper workflow, keeping transcription fully local and avoiding any external API key dependency.

## Product Scope

- Upload one audio/video file in browser
- Optional language hint and prompt
- Execute local Whisper through Python bridge
- Return transcript text + segments + SRT
- Export TXT and SRT from UI

## Architecture

- `app/page.tsx`: landing + studio shell
- `components/transcription-studio.tsx`: upload/settings/results/export
- `app/api/transcriptions/route.ts`: file validation + temp file + local Python execution + normalized JSON response
- `scripts/local_transcribe.py`: bridge script that calls `transcribe.py` functionality
- `lib/transcript.ts`: timestamp and SRT utilities
- `app/api/health/route.ts`: local mode readiness probe

## Security Design

- Secrets are optional; no cloud API keys required
- Strict file type and size validation
- Prompt/language validation via Zod
- Error sanitization in API responses
- Security headers in `next.config.ts`

## Runtime Constraints

- Python dependencies must be installed locally (`requirements-gui.txt`)
- `ffmpeg` must be available for audio decoding
- Upload size limit configurable via `MAX_UPLOAD_MB`

## Testing Strategy

- Unit tests for transcript/SRT utilities
- Typecheck, lint, and production build checks
- Local route health verification
