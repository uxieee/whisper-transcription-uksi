# Whisper Transcription Uksi

A full-stack web transcription app built with Next.js and deployed on Vercel.

## Stack

- Next.js App Router (TypeScript)
- React frontend with a custom responsive studio UI
- Server-side transcription API route (`/api/transcriptions`)
- OpenAI Whisper model (`whisper-1`) for audio transcription

## Features

- Drag/drop upload flow with audio validation
- Optional language and prompt controls
- Timestamped transcript segment view
- Export transcript as `.txt` and subtitles as `.srt`
- Security headers + structured API error responses

## Local Development

1. Install dependencies:

```bash
npm install
```

2. Set environment variables:

```bash
cp .env.example .env.local
```

Add your OpenAI API key in `.env.local`:

```bash
OPENAI_API_KEY=...
```

3. Run dev server:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API

### `POST /api/transcriptions`

`multipart/form-data` fields:

- `file` (required): audio file
- `language` (optional): ISO code (example: `en`, `tl`)
- `prompt` (optional): context prompt for the model

Response:

```json
{
  "data": {
    "text": "...",
    "segments": [],
    "srt": "...",
    "metadata": {
      "fileName": "meeting.m4a",
      "model": "whisper-1",
      "language": "en",
      "durationSeconds": 120.4
    }
  }
}
```

## Limits

- Upload limit is set to 4MB for reliable hosted behavior on Vercel serverless request limits.

## Deploy to Vercel

1. Push this repo to GitHub.
2. Import project in Vercel.
3. Add env var: `OPENAI_API_KEY`.
4. Deploy.
