import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  apiFetch,
  setAccessToken,
  clearAccessToken,
  getAccessToken,
  ApiError,
} from './client';

const mockFetch = vi.fn();
vi.stubGlobal('fetch', mockFetch);

function mockResponse(status: number, body: unknown, ok = status >= 200 && status < 300) {
  return {
    status,
    ok,
    statusText: 'OK',
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(String(body)),
  } as unknown as Response;
}

beforeEach(() => {
  clearAccessToken();
  mockFetch.mockReset();
});

// ── Token management ──────────────────────────────────────────────────────────

describe('setAccessToken / getAccessToken / clearAccessToken', () => {
  it('stores and retrieves a token', () => {
    setAccessToken('my-token');
    expect(getAccessToken()).toBe('my-token');
  });

  it('clears the token', () => {
    setAccessToken('my-token');
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
  });
});

// ── apiFetch — happy path ─────────────────────────────────────────────────────

describe('apiFetch', () => {
  it('makes a GET request to the given path', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { ok: true }));
    await apiFetch('/api/v1/test');
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/v1/test',
      expect.objectContaining({ headers: expect.any(Object) }),
    );
  });

  it('includes Authorization header when token is set', async () => {
    setAccessToken('bearer-token');
    mockFetch.mockResolvedValueOnce(mockResponse(200, {}));
    await apiFetch('/api/v1/test');
    const headers = mockFetch.mock.calls[0][1].headers;
    expect(headers['Authorization']).toBe('Bearer bearer-token');
  });

  it('omits Authorization header when no token', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, {}));
    await apiFetch('/api/v1/test');
    const headers = mockFetch.mock.calls[0][1].headers;
    expect(headers['Authorization']).toBeUndefined();
  });

  it('returns parsed JSON on success', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, { value: 42 }));
    const result = await apiFetch<{ value: number }>('/api/v1/test');
    expect(result.value).toBe(42);
  });

  it('returns null on 204 No Content', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(204, null));
    const result = await apiFetch('/api/v1/test');
    expect(result).toBeNull();
  });

  it('passes request body and method', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(200, {}));
    await apiFetch('/api/v1/test', {
      method: 'POST',
      body: JSON.stringify({ key: 'value' }),
    });
    expect(mockFetch.mock.calls[0][1].method).toBe('POST');
    expect(mockFetch.mock.calls[0][1].body).toBe('{"key":"value"}');
  });
});

// ── apiFetch — error paths ────────────────────────────────────────────────────

describe('apiFetch errors', () => {
  it('throws ApiError on 400', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(400, { detail: 'Bad request' }, false));
    await expect(apiFetch('/api/v1/test')).rejects.toBeInstanceOf(ApiError);
  });

  it('throws ApiError with correct status', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(404, { detail: 'Not found' }, false));
    const err = await apiFetch('/api/v1/test').catch((e) => e);
    expect(err.status).toBe(404);
  });

  it('includes error detail in message', async () => {
    mockFetch.mockResolvedValueOnce(mockResponse(422, { detail: 'Validation failed' }, false));
    const err = await apiFetch('/api/v1/test').catch((e) => e);
    expect(err.message).toBe('Validation failed');
  });

  it('retries with new token after 401 if refresh succeeds', async () => {
    setAccessToken('old-token');
    mockFetch
      .mockResolvedValueOnce(mockResponse(401, {}, false))               // first attempt
      .mockResolvedValueOnce(mockResponse(200, { access_token: 'new' })) // refresh
      .mockResolvedValueOnce(mockResponse(200, { data: 'ok' }));          // retry

    const result = await apiFetch<{ data: string }>('/api/v1/secure');
    expect(result.data).toBe('ok');
    expect(getAccessToken()).toBe('new');
  });

  it('throws ApiError on 401 when refresh also fails', async () => {
    mockFetch
      .mockResolvedValueOnce(mockResponse(401, {}, false))   // first attempt
      .mockResolvedValueOnce(mockResponse(401, {}, false));  // refresh fails

    await expect(apiFetch('/api/v1/secure')).rejects.toBeInstanceOf(ApiError);
  });
});
