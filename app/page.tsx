import { TranscriptionStudio } from "@/components/transcription-studio";

export default function HomePage() {
  return (
    <main className="pageShell">
      <div className="pageGlow pageGlowOne" />
      <div className="pageGlow pageGlowTwo" />
      <section className="hero">
        <p className="eyebrow">Whisper Transcription Uksi</p>
        <h1>Transcribe Audio In A Studio That Feels Crafted, Not Generic.</h1>
        <p className="heroCopy">
          Upload your audio, tune language and context, and export polished transcript + SRT outputs.
          Runs Whisper directly in your browser with no API key and no server-side file upload.
        </p>
      </section>
      <TranscriptionStudio />
    </main>
  );
}
