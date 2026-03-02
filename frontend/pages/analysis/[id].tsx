/**
 * /analysis/[id] — ATHENA analysis results page.
 *
 * Provides a shareable URL for any analysis job.
 * Streams real-time progress via WebSocket then displays results.
 */
import React, { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/router';
import Head from 'next/head';
import Link from 'next/link';
import { getStatus, getResults } from '../../lib/api';
import { useWebSocket } from '../../hooks/useWebSocket';
import { PipelineStatus } from '../../components/PipelineStatus';
import { ResultsDashboard } from '../../components/ResultsDashboard';
import type { StatusResponse, ResultsResponse, PipelineStage } from '../../types/athena';

export default function AnalysisPage() {
  const router = useRouter();
  const jobId = typeof router.query.id === 'string' ? router.query.id : null;

  const [status, setStatus]   = useState<StatusResponse | null>(null);
  const [results, setResults] = useState<ResultsResponse | null>(null);
  const [stage, setStage]     = useState<PipelineStage>('PENDING');
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('Initialising...');
  const [error, setError]     = useState<string | null>(null);

  // Fetch initial status on mount
  useEffect(() => {
    if (!jobId) return;
    getStatus(jobId)
      .then((s) => {
        setStatus(s);
        setStage(s.stage as PipelineStage);
        setProgress(s.progress ?? 0);
        setMessage(s.message ?? '');
        if (s.stage === 'DONE') fetchResults();
        if (s.stage === 'ERROR') setError(s.error ?? 'Analysis failed.');
      })
      .catch(() => setError('Could not load analysis status.'));
  }, [jobId]);

  const fetchResults = useCallback(async () => {
    if (!jobId) return;
    try {
      const r = await getResults(jobId);
      setResults(r);
    } catch {
      setError('Could not load analysis results.');
    }
  }, [jobId]);

  // WebSocket for live updates
  useWebSocket({
    jobId,
    onMessage: (msg) => {
      setStage(msg.stage as PipelineStage);
      setProgress(msg.progress ?? 0);
      setMessage(msg.message ?? '');
      if (msg.stage === 'DONE') fetchResults();
      if (msg.stage === 'ERROR') setError('Analysis encountered an error.');
    },
  });

  const isDone    = stage === 'DONE'  && results !== null;
  const isError   = stage === 'ERROR' || error !== null;
  const isRunning = !isDone && !isError;

  return (
    <>
      <Head>
        <title>
          {status?.target ? `${status.target} — ATHENA` : 'ATHENA Intelligence'}
        </title>
        <meta name="description" content="ATHENA competitive intelligence analysis" />
      </Head>

      <div className="min-h-screen bg-gray-950 text-white">
        {/* Navbar */}
        <nav className="border-b border-gray-800 px-6 py-4 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 text-white hover:text-indigo-300 transition-colors">
            <span className="text-2xl">⚡</span>
            <span className="font-bold text-lg tracking-tight">ATHENA</span>
          </Link>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500 font-mono truncate max-w-[200px]">{jobId}</span>
            <button
              onClick={() => navigator.clipboard?.writeText(window.location.href)}
              className="px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700
                text-xs text-gray-300 transition-colors"
            >
              Copy Link
            </button>
          </div>
        </nav>

        {/* Main content */}
        <main className="max-w-4xl mx-auto px-4 py-10">
          {/* Target header */}
          {status?.target && (
            <div className="mb-8">
              <p className="text-sm text-gray-500 uppercase tracking-wider mb-1">
                {status.target_type} Analysis
              </p>
              <h1 className="text-4xl font-bold text-white">{status.target}</h1>
            </div>
          )}

          {/* Error state */}
          {isError && (
            <div className="p-6 rounded-2xl bg-red-950 border border-red-700 mb-8">
              <h3 className="font-bold text-red-300 mb-2">Analysis Failed</h3>
              <p className="text-sm text-red-400">{error}</p>
              <Link
                href="/"
                className="inline-block mt-4 px-4 py-2 rounded-xl bg-red-800
                  hover:bg-red-700 text-white text-sm transition-colors"
              >
                Start new analysis
              </Link>
            </div>
          )}

          {/* Running state: pipeline progress */}
          {isRunning && (
            <div className="p-6 rounded-2xl bg-gray-900 border border-gray-700 mb-8">
              <h2 className="text-lg font-bold mb-6 text-white">Pipeline Running</h2>
              <PipelineStatus
                currentStage={stage}
                progress={progress}
                message={message}
              />
            </div>
          )}

          {/* Done state: results dashboard */}
          {isDone && results && (
            <ResultsDashboard
              results={results}
              target={status?.target ?? ''}
            />
          )}

          {/* Back link */}
          <div className="mt-10 text-center">
            <Link
              href="/"
              className="text-sm text-gray-500 hover:text-gray-300 transition-colors"
            >
              ← Run another analysis
            </Link>
          </div>
        </main>
      </div>
    </>
  );
}
