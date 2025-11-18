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

    // Some requests (like /start) don't send a body. Attempt to read the body safely,
    // but treat empty bodies as undefined so we don't throw "Unexpected end of JSON input".
    let bodyText: string | undefined;
    try {
      const raw = await request.text();
      if (raw && raw.trim() !== '') {
        bodyText = raw;
      }
    } catch (err) {
      console.error('Failed to read request body:', err);
      bodyText = undefined;
    }

    const response = await fetch(url, {
      method: 'POST',
      headers: bodyText
        ? {
            'Content-Type': 'application/json',
          }
        : undefined,
      body: bodyText,
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
        try {
          data = JSON.parse(text);
        } catch {
          // Not valid JSON - return the text as a message
          console.error('Backend returned non-JSON response:', text.substring(0, 100));
          data = { status: 'ok', message: text.substring(0, 500) };
        }
      }
    } catch (err) {
      // Failed to read response - return success with note
      console.error('Failed to read backend response:', err);
      data = { status: 'ok', note: 'Response could not be read' };
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

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  try {
    const params = await context.params;
    const path = params.path.join('/');
    const url = `${BACKEND_URL}/${path}`;

    // Some requests don't send a body. Attempt to read the body safely.
    let bodyText: string | undefined;
    try {
      const raw = await request.text();
      if (raw && raw.trim() !== '') {
        bodyText = raw;
      }
    } catch (err) {
      console.error('Failed to read request body:', err);
      bodyText = undefined;
    }

    const response = await fetch(url, {
      method: 'PUT',
      headers: bodyText
        ? {
            'Content-Type': 'application/json',
          }
        : undefined,
      body: bodyText,
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
        return NextResponse.json(
          { detail: response.statusText || `Error ${response.status}` },
          { status: response.status }
        );
      }
      
      try {
        const json = JSON.parse(text);
        return NextResponse.json(json, { status: response.status });
      } catch {
        return NextResponse.json(
          { detail: text || response.statusText || `Error ${response.status}` },
          { status: response.status }
        );
      }
    }

    let data;
    try {
      const text = await response.text();
      if (!text || text.trim() === '') {
        data = { status: 'ok' };
      } else {
        try {
          data = JSON.parse(text);
        } catch {
          console.error('Backend returned non-JSON response:', text.substring(0, 100));
          data = { status: 'ok', message: text.substring(0, 500) };
        }
      }
    } catch (err) {
      console.error('Failed to read backend response:', err);
      data = { status: 'ok', note: 'Response could not be read' };
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

