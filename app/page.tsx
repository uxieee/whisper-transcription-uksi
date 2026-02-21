import { TranscriptionStudio } from "@/components/transcription-studio";

export default function HomePage() {
  const currentYear = new Date().getFullYear();

  return (
    <main className="studioPage">
      <header className="mainHeader" aria-label="Main navigation">
        <nav className="topNav">
          <a href="#" aria-label="Pricing">
            Pricing
          </a>
          <a href="#" aria-label="About">
            About
          </a>
        </nav>
        <button type="button" className="profileChip" aria-label="User profile">
          UX
        </button>
      </header>

      <section className="heroSection" aria-label="Hero">
        <h1>Transcription Studio</h1>
        <p>Premium AI-powered accuracy. Effortless flow.</p>
      </section>

      <TranscriptionStudio />

      <footer className="siteFooter" aria-label="Footer">
        <span>© {currentYear} Whisper Transcription Uksi. All rights reserved.</span>
        <div className="footerLinks">
          <a href="#">Privacy Policy</a>
          <a href="#">Terms of Service</a>
        </div>
      </footer>
    </main>
  );
}
