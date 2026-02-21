# Whisper Transcription Uksi Web App Design

## Goal

Convert the existing local Python desktop workflow into a production web app that can be deployed on Vercel with a secure backend, responsive interface, and export-ready transcript artifacts.

## Product Scope

- Upload a single audio file from browser
- Optional language hint and prompt context
- Run transcription through Whisper (`whisper-1`) from a server-side API
- Return transcript text + timestamp segments
- Export TXT and SRT from the UI

Out of scope for this version:

- In-app diarization and DeepFilterNet enhancement
- User authentication, history storage, billing
- Files above hosted request-size limits

## Approach Options

1. Python runtime on hosted functions:
- Pros: reuse existing scripts
- Cons: heavy dependencies (torch/pyannote) are not practical in Vercel serverless limits

2. Next.js frontend + Node API route calling OpenAI Whisper (chosen):
- Pros: Vercel-native deployment, simpler operations, fast implementation
- Cons: depends on external API and key management

3. Split frontend + separate long-running backend worker service:
- Pros: supports larger files and advanced preprocessing
- Cons: more infrastructure complexity for initial launch

## Architecture

- `app/page.tsx`: landing + studio shell
- `components/transcription-studio.tsx`: interactive upload/form/result/export interface
- `app/api/transcriptions/route.ts`: validated file ingestion + OpenAI call + normalized response
- `lib/transcript.ts`: timestamp/segment normalization and SRT utilities
- `app/api/health/route.ts`: lightweight health probe

## API Contract

### `POST /api/transcriptions`

Input: `multipart/form-data`

- `file`: required audio/video file
- `language`: optional ISO language code
- `prompt`: optional text context

Success:

- `data.text`
- `data.segments[]`
- `data.srt`
- `data.metadata`

Errors:

- Structured JSON `{ error: { code, message } }`
- Statuses: `400`, `413`, `415`, `422`, `500`, `502`

## Security Design

- Secrets from environment variables only
- Strict file type + extension + size validation
- Prompt and language validation through Zod schema
- Sanitized server error messages
- Defensive headers in `next.config.ts` (CSP, frame, MIME sniff, referrer policy)

## UX / Frontend Design Direction

Style direction: warm editorial interface with bold geometric typography and atmospheric layered background glows.

- Distinctive typography (`Space Grotesk` + `Space Mono`)
- Fluid type and spacing with `clamp()`
- Container-query responsive segment cards
- Subtle staged load animation and tactile hover behavior

## Testing Strategy

- Unit tests for transcript formatting and normalization utilities
- Typecheck and lint for static validation
- Production build verification

## Deployment Plan

- Push to GitHub repository `whisper-transcription-uksi`
- Create Vercel project with same name
- Configure `OPENAI_API_KEY` in Vercel project environment
- Deploy and validate `/api/health` and end-to-end upload flow
