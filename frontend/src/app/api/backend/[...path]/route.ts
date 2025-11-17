import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  try {
    const params = await context.params;
    const path = params.path.join('/');
    const searchParams = request.nextUrl.searchParams.toString();
    const url = `${BACKEND_URL}/${path}${searchParams ? `?${searchParams}` : ''}`;

    const response = await fetch(url, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const text = await response.text();
      try {
        const json = JSON.parse(text);
        return NextResponse.json(json, { status: response.status });
      } catch {
        return NextResponse.json({ error: text || response.statusText }, { status: response.status });
      }
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (err: unknown) {
    console.error('Backend proxy error:', err);
    return NextResponse.json(
      { error: (err as Error).message || 'Backend request failed' },
      { status: 500 }
    );
  }
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  try {
    const params = await context.params;
    const path = params.path.join('/');
    const url = `${BACKEND_URL}/${path}`;
    const body = await request.json();

    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      cache: 'no-store',
    });

    if (!response.ok) {
      let text = '';
      try {
        text = await response.text();
      } catch {
        text = '';
      }
      
      if (!text || text.trim() === '') {
        // Empty response - return error with status
        return NextResponse.json(
          { detail: response.statusText || `Error ${response.status}` },
          { status: response.status }
        );
      }
      
      try {
        const json = JSON.parse(text);
        return NextResponse.json(json, { status: response.status });
      } catch {
        // Not valid JSON - return as error detail
        return NextResponse.json(
          { detail: text || response.statusText || `Error ${response.status}` },
          { status: response.status }
        );
      }
    }

    // Success response
    let data;
    try {
      const text = await response.text();
      if (!text || text.trim() === '') {
        // Empty success response
        data = { status: 'ok' };
      } else {
        data = JSON.parse(text);
      }
    } catch (err) {
      // Failed to parse - return empty object
      console.error('Failed to parse backend response:', err);
      data = {};
    }
    return NextResponse.json(data);
  } catch (err: unknown) {
    console.error('Backend proxy error:', err);
    return NextResponse.json(
      { detail: (err as Error).message || 'Backend request failed' },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  try {
    const params = await context.params;
    const path = params.path.join('/');
    const url = `${BACKEND_URL}/${path}`;

    const response = await fetch(url, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      cache: 'no-store',
    });

    if (!response.ok) {
      const text = await response.text();
      try {
        const json = JSON.parse(text);
        return NextResponse.json(json, { status: response.status });
      } catch {
        return NextResponse.json({ error: text || response.statusText }, { status: response.status });
      }
    }

    const data = await response.json().catch(() => ({}));
    return NextResponse.json(data);
  } catch (err: unknown) {
    console.error('Backend proxy error:', err);
    return NextResponse.json(
      { error: (err as Error).message || 'Backend request failed' },
      { status: 500 }
    );
  }
}

