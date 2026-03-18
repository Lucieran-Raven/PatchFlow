import { authMiddleware, ClerkRequest } from '@clerk/nextjs';
import { NextResponse } from 'next/server';

export default authMiddleware({
  publicRoutes: [
    '/',
    '/sign-in(.*)',
    '/sign-up(.*)',
    '/api/webhooks(.*)',
    '/api/health',
    '/_next(.*)',
    '/favicon.ico',
    '/logo(.*)',
  ],
  ignoredRoutes: [
    '/api/webhooks/clerk',
  ],
  async beforeAuth(auth: any, req: ClerkRequest) {
    return true;
  },
  async afterAuth(auth: any, req: ClerkRequest) {
    if (!auth.userId && !auth.isPublicRoute) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }
    return NextResponse.next();
  },
});

export const config = {
  matcher: [
    '/((?!.*\\..*|_next).*)',
    '/',
    '/(api|trpc)(.*)',
  ],
};
