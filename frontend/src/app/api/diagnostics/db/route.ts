import { NextResponse } from "next/server";

const API_BASE = process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function GET() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);

  try {
    const res = await fetch(`${API_BASE}/api/diagnostics/db`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
      cache: "no-store",
      signal: controller.signal,
    });

    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      return NextResponse.json(
        {
          status: "error",
          message: `Backend antwortete mit HTTP ${res.status}`,
          backend: data,
        },
        { status: res.status }
      );
    }

    return NextResponse.json(data, { status: res.status });
  } catch (error: any) {
    if (error?.name === "AbortError") {
      return NextResponse.json(
        { status: "error", message: "DB-Diagnostics-Timeout (>15s). Bitte erneut versuchen." },
        { status: 504 }
      );
    }

    return NextResponse.json(
      { status: "error", message: `Backend-Verbindungsfehler: ${error?.message || "Unbekannt"}` },
      { status: 502 }
    );
  } finally {
    clearTimeout(timeout);
  }
}
