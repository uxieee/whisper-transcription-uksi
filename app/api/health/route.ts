import { NextResponse } from "next/server";

export function GET(): Response {
  return NextResponse.json({
    status: "ok",
    hasOpenAIKey: Boolean(process.env.OPENAI_API_KEY)
  });
}
