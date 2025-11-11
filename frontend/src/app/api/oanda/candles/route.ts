import { NextRequest, NextResponse } from "next/server";

const OANDA_HOST = process.env.OANDA_HOST || "https://api-fxpractice.oanda.com";
const OANDA_KEY  = process.env.OANDA_PRACTICE_API_KEY;

export async function GET(req: NextRequest) {
  try {
    if (!OANDA_KEY) {
      return NextResponse.json({ error: "Missing OANDA_PRACTICE_API_KEY" }, { status: 500 });
    }

    const { searchParams } = new URL(req.url);
    const instrument   = searchParams.get("instrument") ?? "EUR_USD";
    const granularity  = searchParams.get("granularity") ?? "M5";  // S5, M1, M5, M15, H1, D
    const count        = searchParams.get("count") ?? "200";        // number of candles
    const price        = searchParams.get("price") ?? "M";          // mid

    const url = `${OANDA_HOST}/v3/instruments/${instrument}/candles?granularity=${granularity}&count=${count}&price=${price}`;

    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${OANDA_KEY}` },
      cache: "no-store",
    });

    if (!res.ok) {
      const text = await res.text();
      return NextResponse.json({ error: text || res.statusText }, { status: res.status });
    }

    const data = await res.json(); // { candles: [...], instrument, granularity }
    return NextResponse.json(data);
  } catch (err: any) {
    return NextResponse.json({ error: err?.message || "Unknown error" }, { status: 500 });
  }
}
