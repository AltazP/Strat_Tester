import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const path = request.nextUrl.pathname;

  const isPublicPath = path === '/login' || 
                       path.startsWith('/api/auth/verify') ||
                       path.startsWith('/_next') ||
                       path.startsWith('/favicon.ico') ||
                       path.startsWith('/images');

  if (isPublicPath) {
    return NextResponse.next();
  }

  const authToken = request.cookies.get('auth_token')?.value;
  
  if (!authToken) {
    if (path.startsWith('/api')) {
      return NextResponse.json(
        { error: 'Unauthorized' },
        { status: 401 }
      );
    }
    
    return NextResponse.redirect(new URL('/login', request.url));
  }

  if (path === '/login' && authToken) {
    return NextResponse.redirect(new URL('/', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!_next/static|_next/image|_next/webpack-hmr|favicon.ico|api/auth/verify).*)',
  ],
};

