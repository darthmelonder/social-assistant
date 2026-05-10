/**
 * Base API client.
 *
 * Manages the in-memory access token and transparently retries a request
 * once after a token refresh on 401. Redirects to '/' if refresh also fails.
 */

const API_BASE = (import.meta as unknown as { env: Record<string, string> }).env?.VITE_API_URL ?? '';

let _accessToken: string | null = null;

export function setAccessToken(token: string): void {
  _accessToken = token;
}

export function clearAccessToken(): void {
  _accessToken = null;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await _fetch(path, init, _accessToken);

  if (response.status === 401) {
    const refreshed = await _tryRefresh();
    if (refreshed) {
      const retry = await _fetch(path, init, _accessToken);
      return _parseResponse<T>(retry);
    }
    clearAccessToken();
    if (typeof window !== 'undefined') window.location.href = '/';
    throw new ApiError(401, 'Session expired');
  }

  return _parseResponse<T>(response);
}

// ── Internal helpers ──────────────────────────────────────────────────────────

async function _fetch(path: string, init: RequestInit, token: string | null): Promise<Response> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  return fetch(`${API_BASE}${path}`, { ...init, headers });
}

async function _tryRefresh(): Promise<boolean> {
  try {
    const resp = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    if (!resp.ok) return false;
    const { access_token } = (await resp.json()) as { access_token: string };
    setAccessToken(access_token);
    return true;
  } catch {
    return false;
  }
}

async function _parseResponse<T>(resp: Response): Promise<T> {
  if (resp.status === 204) return null as T;
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {}
    throw new ApiError(resp.status, detail);
  }
  return resp.json() as Promise<T>;
}
