import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.INTERNAL_API_URL || 'http://kafin-backend:8000';

export const maxDuration = 120;

export async function POST(request: NextRequest) {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 115000);

    const res = await fetch(`${BACKEND_URL}/api/reports/generate-morning`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
    });

    clearTimeout(timeout);

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    if (error?.name === 'AbortError') {
      return NextResponse.json(
        { status: 'error', message: 'Morning Briefing Timeout (>115s). Bitte erneut versuchen.' },
        { status: 504 }
      );
    }
    return NextResponse.json(
      { status: 'error', message: `Backend-Verbindungsfehler: ${error?.message || 'Unbekannt'}` },
      { status: 502 }
    );
  }
}
