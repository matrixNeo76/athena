// ---------------------------------------------------------------------------
// ATHENA — REST + WebSocket API client
// ---------------------------------------------------------------------------
import type {
  StartRequest,
  StartResponse,
  StatusResponse,
  ResultsResponse,
} from '../types/athena';

/** Resolved from env; falls back to same-origin (for Vercel / NGINX proxy). */
const BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, '') || '';

/** Default fetch timeout in milliseconds. */
const DEFAULT_TIMEOUT_MS = 30_000;

/** Typed API error with HTTP status code. */
export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/**
 * Core fetch wrapper with:
 *  - Content-Type: application/json header
 *  - Configurable timeout via AbortController
 *  - Typed ApiError on non-2xx responses
 */
async function apiFetch<T>(
  path: string,
  init?: RequestInit & { timeoutMs?: number },
): Promise<T> {
  const timeoutMs = init?.timeoutMs ?? DEFAULT_TIMEOUT_MS;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
      signal: controller.signal,
      ...init,
    });

    if (!res.ok) {
      const body = await res.text().catch(() => '');
      throw new ApiError(res.status, `[${res.status}] ${body || res.statusText}`);
    }

    return res.json() as Promise<T>;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiError(408, `Request timed out after ${timeoutMs}ms: ${path}`);
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/** POST /api/v1/analysis/start */
export function startAnalysis(req: StartRequest): Promise<StartResponse> {
  return apiFetch<StartResponse>('/api/v1/analysis/start', {
    method: 'POST',
    body: JSON.stringify(req),
    timeoutMs: 15_000,
  });
}

/** GET /api/v1/analysis/{job_id}/status */
export function getStatus(jobId: string): Promise<StatusResponse> {
  return apiFetch<StatusResponse>(`/api/v1/analysis/${jobId}/status`, {
    timeoutMs: 10_000,
  });
}

/** GET /api/v1/analysis/{job_id}/results */
export function getResults(jobId: string): Promise<ResultsResponse> {
  return apiFetch<ResultsResponse>(`/api/v1/analysis/${jobId}/results`, {
    timeoutMs: 30_000,
  });
}

/** Build WebSocket URL for a given job (replaces http with ws). */
export function buildWsUrl(jobId: string): string {
  // NEXT_PUBLIC_API_URL is the authoritative source for the backend address.
  // If not set, fall back to window.location.origin (same-origin proxy mode).
  // NOTE: window.location is only available client-side; this function must
  // only be called from browser event handlers (never during SSR).
  const base = BASE || (typeof window !== 'undefined' ? window.location.origin : '');
  const wsBase = base.replace(/^http/, 'ws');
  return `${wsBase}/ws/analysis/${jobId}/progress`;
}
