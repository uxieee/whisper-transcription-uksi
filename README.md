# Whisper Transcription Uksi

A local-first web transcription app that runs Whisper directly in the browser.

## Key Points

- No API key required
- No server upload for transcription
- Model runs client-side in a Web Worker
- Export transcript as `.txt` and subtitles as `.srt`

## Stack

- Next.js App Router (TypeScript)
- React frontend + Web Worker
- `@huggingface/transformers` for in-browser Whisper inference

## Setup

1. Install dependencies:

```bash
npm install
```

2. Run app:

```bash
npm run dev
```

3. Open [http://localhost:3000](http://localhost:3000)

## Notes

- First transcription downloads model files in-browser (can be large).
- After caching, subsequent runs are faster.
- Browser performance depends on your device and whether WebGPU is available.

## Optional Legacy Local-Python Route

This repo still includes a local Python API bridge (`/api/transcriptions` + `scripts/local_transcribe.py`) if you want server-side local transcription inside your machine.
