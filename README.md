# Whisper Transcription Uksi

A local-first web transcription app built with Next.js + Python Whisper.

## What This Version Does

- Runs transcription locally on your machine (no OpenAI API key)
- Upload audio/video in the browser
- Optional language and prompt hints
- Returns timestamped segments
- Export transcript as `.txt` and subtitles as `.srt`

## Tech Stack

- Next.js App Router (TypeScript)
- React frontend studio UI
- Node route handler (`/api/transcriptions`) that calls local Python
- Existing Python Whisper pipeline in `transcribe.py`

## Prerequisites

- Node.js 20+
- Python 3.9+
- `ffmpeg` available on PATH

## Setup

1. Install Node dependencies:

```bash
npm install
```

2. Create a Python virtual environment and install Python deps:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-gui.txt
```

3. Configure environment variables:

```bash
cp .env.example .env.local
```

Defaults already work for most local setups. If needed, point to your Python explicitly:

```bash
LOCAL_PYTHON_BIN=./venv/bin/python
```

4. Run the web app:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## API

### `POST /api/transcriptions`

`multipart/form-data` fields:

- `file` (required): audio file
- `language` (optional): ISO code (example: `en`, `tl`)
- `prompt` (optional): context prompt

Success response:

```json
{
  "data": {
    "text": "...",
    "segments": [],
    "srt": "...",
    "metadata": {
      "fileName": "meeting.m4a",
      "model": "turbo",
      "language": "en",
      "durationSeconds": 120.4,
      "runtime": "local-python"
    }
  }
}
```

## Local Health Check

```bash
curl http://localhost:3000/api/health
```

Example:

```json
{
  "status": "ok",
  "mode": "local-python",
  "localScriptReady": true,
  "model": "turbo"
}
```
