# Whisper Transcription Uksi

A local-first transcription web app.

## How this project currently works

This repo has **two local modes**:

1. **Browser Worker mode (default in UI)**
- Frontend decodes audio and sends samples to `components/whisper.worker.ts`
- Worker loads Whisper models through `@huggingface/transformers`
- Model files are downloaded/cached in the browser on first run
- No server upload for the transcription path

2. **Local Python bridge mode (optional legacy route)**
- API route: `app/api/transcriptions/route.ts`
- Python bridge: `scripts/local_transcribe.py` -> `transcribe.py`
- Runs Whisper on your machine (CPU/GPU/MPS) through Python
- Useful if you want non-browser execution or tighter local infra control

## Is Hugging Face required?

- **Required only for Browser Worker mode**, because model assets are fetched by Transformers.js.
- **Not required for Python Whisper transcription itself** (except optional pyannote diarization token flow in `transcribe.py`).

So if you decide to use only the Python local route, you can avoid the browser Hugging Face worker path.

## Whisper models available in the web app

The model picker includes:
- `Xenova/whisper-tiny`
- `Xenova/whisper-tiny.en`
- `Xenova/whisper-base`
- `Xenova/whisper-base.en`
- `Xenova/whisper-small`
- `Xenova/whisper-small.en`
- `Xenova/whisper-medium`
- `Xenova/whisper-medium.en`
- `Xenova/whisper-large-v1`
- `Xenova/whisper-large-v2`
- `Xenova/whisper-large-v3`
- `onnx-community/whisper-large-v3-turbo`

## Stack

- Next.js App Router (TypeScript)
- React frontend + Web Worker
- `@huggingface/transformers` for in-browser Whisper inference
- Optional Node API + Python local bridge

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

- First worker transcription can be slow due to model download.
- Cached runs are faster.
- Very large Whisper models may be heavy for low-memory devices.
