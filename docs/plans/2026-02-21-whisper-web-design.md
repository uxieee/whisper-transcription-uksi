# Whisper Transcription Uksi Web App Design

## Goal

Deliver a web UI where Whisper transcription runs locally on the user's machine inside the browser, similar to Hugging Face Whisper web demos.

## Product Scope

- Upload a single audio/video file in browser
- Optional language selection
- Run Whisper in-browser via Web Worker
- Render text + timestamped segments
- Export TXT and SRT

## Architecture

- `app/page.tsx`: landing and studio shell
- `components/transcription-studio.tsx`: UI state, worker orchestration, exports
- `components/whisper.worker.ts`: browser-side model loading and ASR execution
- `lib/transcript.ts`: timestamp and SRT formatting helpers

## Runtime

- Uses `@huggingface/transformers` with Whisper model IDs (`Xenova/whisper-*`)
- No OpenAI API key required
- No server upload for main transcription flow

## Security

- Files stay local to browser for transcription path
- Existing security headers remain in Next.js config
- Input validation remains in optional API route

## Tradeoffs

- First run is slower due to model download
- Model size directly impacts speed/accuracy
- Browser/hardware capability affects performance
