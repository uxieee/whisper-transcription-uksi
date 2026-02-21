import type { Metadata } from "next";
import { Space_Grotesk, Space_Mono } from "next/font/google";
import "./globals.css";

const headingFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading"
});

const bodyFont = Space_Mono({
  subsets: ["latin"],
  weight: ["400", "700"],
  variable: "--font-body"
});

export const metadata: Metadata = {
  title: "Whisper Transcription Uksi",
  description: "Beautiful web studio for fast audio transcription with Whisper on Vercel."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${headingFont.variable} ${bodyFont.variable}`}>
      <body>{children}</body>
    </html>
  );
}
