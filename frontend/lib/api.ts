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

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`[${res.status}] ${body || res.statusText}`);
  }
  return res.json() as Promise<T>;
}

/** POST /api/v1/analysis/start */
export function startAnalysis(req: StartRequest): Promise<StartResponse> {
  return apiFetch<StartResponse>('/api/v1/analysis/start', {
    method: 'POST',
    body: JSON.stringify(req),
  });
}

/** GET /api/v1/analysis/{job_id}/status */
export function getStatus(jobId: string): Promise<StatusResponse> {
  return apiFetch<StatusResponse>(`/api/v1/analysis/${jobId}/status`);
}

/** GET /api/v1/analysis/{job_id}/results */
export function getResults(jobId: string): Promise<ResultsResponse> {
  return apiFetch<ResultsResponse>(`/api/v1/analysis/${jobId}/results`);
}

/** Build WebSocket URL for a given job (replaces http with ws). */
export function buildWsUrl(jobId: string): string {
  const base = BASE || window.location.origin;
  const wsBase = base.replace(/^http/, 'ws');
  return `${wsBase}/ws/analysis/${jobId}/progress`;
}
