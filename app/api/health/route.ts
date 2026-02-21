import path from "node:path";
import { promises as fs } from "node:fs";
import { NextResponse } from "next/server";

const LOCAL_SCRIPT_PATH = path.join(process.cwd(), "scripts", "local_transcribe.py");

export async function GET(): Promise<Response> {
  let localScriptReady = false;

  try {
    await fs.access(LOCAL_SCRIPT_PATH);
    localScriptReady = true;
  } catch {
    localScriptReady = false;
  }

  return NextResponse.json({
    status: "ok",
    mode: "local-python",
    localScriptReady,
    model: process.env.LOCAL_WHISPER_MODEL?.trim() || "turbo"
  });
}
