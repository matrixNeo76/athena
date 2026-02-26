import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  Fragment,
} from 'react';
import type { GetServerSideProps } from 'next';
import Head from 'next/head';
import type {
  AnalysisType,
  PipelineStage,
  WsProgressMessage,
  ResultsResponse,
  DeckSlide,
} from '../types/athena';

import { startAnalysis, getStatus, getResults, buildWsUrl } from '../lib/api';

// Opt out of static prerendering — this page uses browser APIs (WebSocket, navigator.clipboard)
export const getServerSideProps: GetServerSideProps = async () => ({ props: {} });

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ORDERED_STAGES: PipelineStage[] = [
  'SCOUT',
  'ANALYST',
  'STRATEGY',
  'PRESENTER',
];

const STAGE_EMOJI: Record<string, string> = {
  SCOUT:     '🔍',
  ANALYST:   '📊',
  STRATEGY:  '♟️',
  PRESENTER: '📽️',
};

const STAGE_LABEL: Record<string, string> = {
  SCOUT:     'Scout',
  ANALYST:   'Analyst',
  STRATEGY:  'Strategy',
  PRESENTER: 'Presenter',
};

type AppStatus = 'idle' | 'running' | 'done' | 'error';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

/** Four-step pipeline timeline */
const Timeline: React.FC<{ currentStage: PipelineStage }> = ({ currentStage }) => {
  const currentIdx = ORDERED_STAGES.indexOf(currentStage);
  const isDone = currentStage === 'DONE';

  return (
    <div className="timeline">
      {ORDERED_STAGES.map((stage, i) => {
        const isCompleted = isDone || currentIdx > i;
        const isActive    = stage === currentStage;

        return (
          <Fragment key={stage}>
            {/* Step */}
            <div
              className={[
                'tl-step',
                isActive    ? 'tl-active' : '',
                isCompleted ? 'tl-done'   : '',
              ].join(' ')}
            >
              <div className="tl-dot">
                {isCompleted ? '✓' : i + 1}
              </div>
              <div className="tl-label">
                {STAGE_EMOJI[stage]} {STAGE_LABEL[stage]}
              </div>
            </div>

            {/* Connector line (not after last step) */}
            {i < ORDERED_STAGES.length - 1 && (
              <div className={`tl-line ${isCompleted ? 'tl-done' : ''}`} />
            )}
          </Fragment>
        );
      })}
    </div>
  );
};

/** Single deck slide card */
const SlideCard: React.FC<{ slide: DeckSlide }> = ({ slide }) => (
  <div className="slide-card">
    <div className="slide-num">Slide {slide.slide_number}</div>
    <div className="slide-title">{slide.title}</div>
    {slide.subtitle && (
      <div className="slide-subtitle">{slide.subtitle}</div>
    )}
    {slide.bullets && slide.bullets.length > 0 && (
      <ul className="slide-bullets">
        {slide.bullets.map((b, idx) => (
          // Composite key prevents warning when multiple SlideCards are rendered
          <li key={`s${slide.slide_number}-b${idx}`}>{b}</li>
        ))}
      </ul>
    )}
    {slide.speaker_note && (
      <div className="speaker-note">💬 {slide.speaker_note}</div>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Home() {
  // ---- Form state ----------------------------------------------------------
  const [target, setTarget]    = useState('');
  const [type,   setType]      = useState<AnalysisType>('company');
  const [loading, setLoading]  = useState(false);

  // ---- Pipeline state ------------------------------------------------------
  const [appStatus,     setAppStatus]     = useState<AppStatus>('idle');
  const [jobId,         setJobId]         = useState<string | null>(null);
  const [currentStage,  setCurrentStage]  = useState<PipelineStage>('PENDING');
  const [progress,      setProgress]      = useState(0);
  const [messages,      setMessages]      = useState<string[]>([]);
  const [results,       setResults]       = useState<ResultsResponse | null>(null);
  const [errorMsg,      setErrorMsg]      = useState<string | null>(null);
  const [copyHint,      setCopyHint]      = useState(false);

  // ---- Refs ----------------------------------------------------------------
  const wsRef          = useRef<WebSocket | null>(null);
  const pollRef        = useRef<ReturnType<typeof setInterval> | null>(null);
  const logBottomRef   = useRef<HTMLDivElement>(null);
  const wsOpenedRef    = useRef(false);   // guard: did WS ever open?

  // ---- Auto-scroll log -----------------------------------------------------
  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ---- Helpers -------------------------------------------------------------
  const addMessage = useCallback((text: string, kind: 'info' | 'error' | 'done' = 'info') => {
    const ts  = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const cls = kind === 'error' ? 'log-error' : kind === 'done' ? 'log-done' : '';
    // store as "CLASS|||TEXT" so we can render with the right class
    setMessages(prev => [...prev, `${cls}|||[${ts}] ${text}`]);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const handleDone = useCallback(async (jId: string) => {
    stopPolling();
    setCurrentStage('DONE');
    setProgress(100);
    setAppStatus('done');
    addMessage('✅ Pipeline complete — fetching results…', 'done');
    try {
      const res = await getResults(jId);
      setResults(res);
      addMessage('Results loaded.', 'done');
    } catch (e: unknown) {
      addMessage(`Could not load results: ${e instanceof Error ? e.message : String(e)}`, 'error');
    }
  }, [addMessage, stopPolling]);

  const handleError = useCallback((msg: string) => {
    stopPolling();
    setAppStatus('error');
    setErrorMsg(msg);
    addMessage(`❌ ${msg}`, 'error');
  }, [addMessage, stopPolling]);

  // ---- Polling fallback ----------------------------------------------------
  const startPolling = useCallback((jId: string) => {
    addMessage('WebSocket unavailable — polling every 2 s…');
    pollRef.current = setInterval(async () => {
      try {
        const s = await getStatus(jId);
        setCurrentStage(s.stage);
        setProgress(s.progress);
        if (s.message) addMessage(s.message);

        if (s.stage === 'DONE') {
          stopPolling();
          handleDone(jId);
        } else if (s.stage === 'ERROR') {
          handleError(s.error_message ?? 'Pipeline error');
        }
      } catch {
        // transient network blip — keep polling
      }
    }, 2000);
  }, [addMessage, handleDone, handleError, stopPolling]);

  // ---- WebSocket connection ------------------------------------------------
  const connectWebSocket = useCallback((jId: string) => {
    addMessage('Connecting to pipeline stream…');
    wsOpenedRef.current = false;

    const url = buildWsUrl(jId);
    const ws  = new WebSocket(url);
    wsRef.current = ws;

    // Fallback timer: if WS hasn't opened in 5 s, switch to polling
    const fallback = setTimeout(() => {
      if (!wsOpenedRef.current) {
        ws.close();
        startPolling(jId);
      }
    }, 5000);

    ws.onopen = () => {
      wsOpenedRef.current = true;
      clearTimeout(fallback);
      addMessage('Stream connected.');
    };

    ws.onmessage = (evt) => {
      try {
        const msg: WsProgressMessage = JSON.parse(evt.data as string);
        setCurrentStage(msg.stage);
        setProgress(msg.progress);
        if (msg.message) addMessage(msg.message);

        if (msg.stage === 'DONE') {
          ws.close();
          handleDone(jId);
        } else if (msg.stage === 'ERROR') {
          ws.close();
          handleError(msg.message || 'Pipeline error');
        }
      } catch {
        // Non-JSON frame — display raw
        if (evt.data) addMessage(String(evt.data));
      }
    };

    ws.onerror = () => {
      clearTimeout(fallback);
      if (!wsOpenedRef.current) startPolling(jId);
    };

    ws.onclose = () => clearTimeout(fallback);
  }, [addMessage, handleDone, handleError, startPolling]);

  // ---- Submit --------------------------------------------------------------
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim() || loading) return;

    // Reset all pipeline state
    setLoading(true);
    setAppStatus('running');
    setMessages([]);
    setCurrentStage('PENDING');
    setProgress(0);
    setResults(null);
    setErrorMsg(null);
    setCopyHint(false);

    try {
      addMessage(`Starting ATHENA analysis for "${target.trim()}" (${type})…`);
      const { job_id } = await startAnalysis({ target: target.trim(), type });
      setJobId(job_id);
      addMessage(`Job created: ${job_id}`);
      connectWebSocket(job_id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to start analysis';
      handleError(msg);
    } finally {
      setLoading(false);
    }
  }, [target, type, loading, addMessage, connectWebSocket, handleError]);

  // ---- Reset ---------------------------------------------------------------
  const handleReset = useCallback(() => {
    wsRef.current?.close();
    stopPolling();
    setAppStatus('idle');
    setJobId(null);
    setCurrentStage('PENDING');
    setProgress(0);
    setMessages([]);
    setResults(null);
    setErrorMsg(null);
  }, [stopPolling]);

  // ---- Copy report ---------------------------------------------------------
  const handleCopy = useCallback(() => {
    const md = results?.presenter_result?.report_markdown ?? '';
    // navigator.clipboard is only available in secure contexts (HTTPS / localhost)
    if (!navigator?.clipboard) {
      addMessage('Clipboard not available in this context.', 'error');
      return;
    }
    navigator.clipboard.writeText(md)
      .then(() => {
        setCopyHint(true);
        setTimeout(() => setCopyHint(false), 2000);
      })
      .catch(() => addMessage('Clipboard write failed — copy manually.', 'error'));
  }, [results, addMessage]);

  // ---- Cleanup on unmount --------------------------------------------------
  useEffect(() => {
    return () => {
      wsRef.current?.close();
      stopPolling();
    };
  }, [stopPolling]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <>
      <Head>
        <title>ATHENA — Market Intelligence Platform</title>
        <meta name="description" content="Autonomous Multi-Agent Market Intelligence & Strategy" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="app">

        {/* ── Header ──────────────────────────────────────────────────────── */}
        <header className="header">
          <div className="header-inner">
            <div className="logo">
              <span className="logo-icon">⚡</span>
              <span className="logo-text">ATHENA</span>
            </div>
            <p className="tagline">Autonomous Multi-Agent Market Intelligence &amp; Strategy</p>
          </div>
        </header>

        <main className="main">

          {/* ── IDLE: Input form ────────────────────────────────────────── */}
          {appStatus === 'idle' && (
            <section className="card form-card">
              <h2 className="section-title">New Analysis</h2>
              <form onSubmit={handleSubmit} className="form">
                <div className="field">
                  <label className="label" htmlFor="target">Target</label>
                  <input
                    id="target"
                    className="input"
                    type="text"
                    value={target}
                    onChange={e => setTarget(e.target.value)}
                    placeholder="e.g. OpenAI, Stripe, DeFi lending protocols…"
                    required
                    autoFocus
                  />
                </div>
                <div className="field">
                  <label className="label" htmlFor="type">Analysis Type</label>
                  <select
                    id="type"
                    className="input select"
                    value={type}
                    onChange={e => setType(e.target.value as AnalysisType)}
                  >
                    <option value="company">🏢 Company</option>
                    <option value="product">📦 Product</option>
                    <option value="market">🌍 Market</option>
                  </select>
                </div>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!target.trim() || loading}
                >
                  ⚡ Run ATHENA
                </button>
              </form>
            </section>
          )}

          {/* ── RUNNING / DONE: Pipeline view ───────────────────────────── */}
          {(appStatus === 'running' || appStatus === 'done') && (
            <>
              {/* Status card */}
              <section className="card">
                <div className="job-header">
                  <div>
                    <h2 className="section-title">
                      {appStatus === 'done' ? '✅ Analysis Complete' : '⚡ Running Analysis'}
                    </h2>
                    <div className="job-meta">
                      <span className="tag">{type}</span>
                      <span className="job-target">{target}</span>
                      {jobId && (
                        <span className="job-id">#{jobId.slice(0, 8)}</span>
                      )}
                    </div>
                  </div>
                  {appStatus === 'done' && (
                    <button className="btn btn-secondary" onClick={handleReset}>
                      New Analysis
                    </button>
                  )}
                </div>

                {/* Timeline */}
                <Timeline currentStage={currentStage} />

                {/* Progress bar */}
                <div className="progress-track">
                  <div className="progress-bar" style={{ width: `${progress}%` }} />
                </div>
                <p className="progress-label">{progress}%</p>
              </section>

              {/* Log */}
              <section className="card log-card">
                <p className="section-title-sm">Pipeline Log</p>
                <div className="log">
                  {messages.map((raw, i) => {
                    const [cls, text] = raw.includes('|||') ? raw.split('|||') : ['', raw];
                    // Use index key: safe for append-only lists; trim to avoid trailing space
                    return (
                      <div key={i} className={['log-line', cls].filter(Boolean).join(' ')}>{text}</div>
                    );
                  })}
                  <div ref={logBottomRef} />
                </div>
              </section>

              {/* Results (only when DONE and data available) */}
              {appStatus === 'done' && results?.presenter_result && (
                <>
                  {/* Markdown report */}
                  <section className="card">
                    <div className="results-header">
                      <p className="section-title-sm">📄 Market Intelligence Report</p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        {copyHint && <span className="copy-hint">Copied!</span>}
                        <button className="btn btn-ghost" onClick={handleCopy}>
                          Copy
                        </button>
                      </div>
                    </div>
                    <textarea
                      className="report-area"
                      readOnly
                      value={results.presenter_result.report_markdown}
                      spellCheck={false}
                    />
                  </section>

                  {/* Deck outline */}
                  <section className="card">
                    <p className="section-title-sm">
                      🎯 Deck Outline &nbsp;
                      <span style={{ opacity: 0.5, fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>
                        ({results.presenter_result.deck_outline.length} slides)
                      </span>
                    </p>
                    <div className="deck-grid">
                      {results.presenter_result.deck_outline.map((slide: DeckSlide) => (
                        <SlideCard key={slide.slide_number} slide={slide} />
                      ))}
                    </div>
                  </section>
                </>
              )}
            </>
          )}

          {/* ── ERROR ───────────────────────────────────────────────────── */}
          {appStatus === 'error' && (
            <section className="card error-card">
              <h2 className="section-title">❌ Analysis Failed</h2>
              <pre className="error-msg">{errorMsg}</pre>
              <button className="btn btn-secondary" onClick={handleReset}>
                Try Again
              </button>
            </section>
          )}

        </main>

        <footer className="footer">
          ATHENA · Built for Complete AI Hackathon · Powered by Deploy.AI
        </footer>
      </div>
    </>
  );
}
