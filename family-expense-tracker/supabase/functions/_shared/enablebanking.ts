// Shared Enable Banking API helper: JWT signing + fetch wrapper.
import { SignJWT, importPKCS8 } from 'npm:jose@5';

const EB_API = 'https://api.enablebanking.com';

export async function ebJwt(): Promise<string> {
  const appId = Deno.env.get('EB_APP_ID');
  const pem = Deno.env.get('EB_PRIVATE_KEY');
  if (!appId || !pem) throw new Error('EB_APP_ID / EB_PRIVATE_KEY not configured');
  const key = await importPKCS8(pem.replace(/\\n/g, '\n'), 'RS256');
  const now = Math.floor(Date.now() / 1000);
  return await new SignJWT({})
    .setProtectedHeader({ alg: 'RS256', typ: 'JWT', kid: appId })
    .setIssuer('enablebanking.com')
    .setAudience('api.enablebanking.com')
    .setIssuedAt(now)
    .setExpirationTime(now + 3600)
    .sign(key);
}

export async function eb(path: string, init: RequestInit = {}): Promise<Response> {
  const jwt = await ebJwt();
  return await fetch(`${EB_API}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${jwt}`,
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  });
}
