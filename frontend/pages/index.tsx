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
  SWOTModel,
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
  SCOUT:     '\uD83D\uDD0D',
  ANALYST:   '\uD83D\uDCCA',
  STRATEGY:  '\u265F\uFE0F',
  PRESENTER: '\uD83C\uDFBD',
};

const STAGE_LABEL: Record<string, string> = {
  SCOUT:     'Scout',
  ANALYST:   'Analyst',
  STRATEGY:  'Strategy',
  PRESENTER: 'Presenter',
};

/** Maximum number of log lines kept in memory to prevent unbounded growth */
const MAX_LOG_LINES = 500;

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
              ].filter(Boolean).join(' ')}
            >
              <div className="tl-dot">
                {isCompleted ? '\u2713' : i + 1}
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

/** SWOT quadrant */
const SWOTQuadrant: React.FC<{
  label: string;
  items: string[];
  kind: 's' | 'w' | 'o' | 't';
}> = ({ label, items, kind }) => (
  <div className={`swot-quadrant swot-${kind}`}>
    <div className="swot-label">{label}</div>
    <ul className="swot-items">
      {items.map((item, i) => <li key={i}>{item}</li>)}
    </ul>
  </div>
);

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
          <li key={`s${slide.slide_number}-b${idx}`}>{b}</li>
        ))}
      </ul>
    )}
    {slide.speaker_note && (
      <div className="speaker-note">\uD83D\uDCAC {slide.speaker_note}</div>
    )}
  </div>
);

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Home() {
  // ---- Form state ----------------------------------------------------------
  const [target, setTarget]   = useState('');
  const [type,   setType]     = useState<AnalysisType>('company');
  const [loading, setLoading] = useState(false);

  // ---- Pipeline state ------------------------------------------------------
  const [appStatus,    setAppStatus]    = useState<AppStatus>('idle');
  const [jobId,        setJobId]        = useState<string | null>(null);
  const [currentStage, setCurrentStage] = useState<PipelineStage>('PENDING');
  const [progress,     setProgress]     = useState(0);
  const [messages,     setMessages]     = useState<string[]>([]);
  const [results,      setResults]      = useState<ResultsResponse | null>(null);
  const [errorMsg,     setErrorMsg]     = useState<string | null>(null);
  const [copyHint,     setCopyHint]     = useState(false);

  // ---- Refs ----------------------------------------------------------------
  const wsRef        = useRef<WebSocket | null>(null);
  const pollRef      = useRef<ReturnType<typeof setInterval> | null>(null);
  const logBottomRef = useRef<HTMLDivElement>(null);
  const wsOpenedRef  = useRef(false);

  // ---- Auto-scroll log -----------------------------------------------------
  useEffect(() => {
    logBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // ---- Helpers -------------------------------------------------------------
  const addMessage = useCallback((
    text: string,
    kind: 'info' | 'error' | 'done' = 'info',
  ) => {
    const ts  = new Date().toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    });
    const cls = kind === 'error' ? 'log-error' : kind === 'done' ? 'log-done' : '';
    setMessages(prev => {
      const next = [...prev, `${cls}|||[${ts}] ${text}`];
      return next.length > MAX_LOG_LINES ? next.slice(-MAX_LOG_LINES) : next;
    });
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const handleDone = useCallback(async (jId: string) => {
    stopPolling();
    setCurrentStage('DONE');
    setProgress(100);
    setAppStatus('done');
    addMessage('\u2705 Pipeline complete \u2014 fetching results\u2026', 'done');
    try {
      const res = await getResults(jId);
      setResults(res);
      addMessage('Results loaded.', 'done');
    } catch (e: unknown) {
      addMessage(
        `Could not load results: ${e instanceof Error ? e.message : String(e)}`,
        'error',
      );
    }
  }, [addMessage, stopPolling]);

  const handleError = useCallback((msg: string) => {
    stopPolling();
    setAppStatus('error');
    setErrorMsg(msg);
    addMessage(`\u274C ${msg}`, 'error');
  }, [addMessage, stopPolling]);

  // ---- Polling fallback ----------------------------------------------------
  const startPolling = useCallback((jId: string) => {
    addMessage('WebSocket unavailable \u2014 polling every 2 s\u2026');
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
        // transient network blip \u2014 keep polling
      }
    }, 2000);
  }, [addMessage, handleDone, handleError, stopPolling]);

  // ---- WebSocket connection ------------------------------------------------
  const connectWebSocket = useCallback((jId: string) => {
    addMessage('Connecting to pipeline stream\u2026');
    wsOpenedRef.current = false;

    const url = buildWsUrl(jId);
    const ws  = new WebSocket(url);
    wsRef.current = ws;

    const fallback = setTimeout(() => {
      if (!wsOpenedRef.current) { ws.close(); startPolling(jId); }
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
        if (msg.stage === 'DONE') { ws.close(); handleDone(jId); }
        else if (msg.stage === 'ERROR') { ws.close(); handleError(msg.message || 'Pipeline error'); }
      } catch {
        if (evt.data) addMessage(String(evt.data));
      }
    };

    ws.onerror = () => { clearTimeout(fallback); if (!wsOpenedRef.current) startPolling(jId); };
    ws.onclose = () => clearTimeout(fallback);
  }, [addMessage, handleDone, handleError, startPolling]);

  // ---- Submit --------------------------------------------------------------
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim() || loading) return;

    setLoading(true);
    setAppStatus('running');
    setMessages([]);
    setCurrentStage('PENDING');
    setProgress(0);
    setResults(null);
    setErrorMsg(null);
    setCopyHint(false);

    try {
      addMessage(`Starting ATHENA analysis for "${target.trim()}" (${type})\u2026`);
      const { job_id } = await startAnalysis({ target: target.trim(), type });
      setJobId(job_id);
      addMessage(`Job created: ${job_id}`);
      connectWebSocket(job_id);
    } catch (err: unknown) {
      handleError(err instanceof Error ? err.message : 'Failed to start analysis');
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
    if (!navigator?.clipboard) {
      addMessage('Clipboard not available in this context.', 'error');
      return;
    }
    navigator.clipboard.writeText(md)
      .then(() => { setCopyHint(true); setTimeout(() => setCopyHint(false), 2000); })
      .catch(() => addMessage('Clipboard write failed \u2014 copy manually.', 'error'));
  }, [results, addMessage]);

  // ---- Cleanup on unmount --------------------------------------------------
  useEffect(() => {
    return () => { wsRef.current?.close(); stopPolling(); };
  }, [stopPolling]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <>
      <Head>
        <title>ATHENA \u2014 Market Intelligence Platform</title>
        <meta name="description" content="Autonomous Multi-Agent Market Intelligence &amp; Strategy" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="app">

        {/* \u2500\u2500 Header \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */}
        <header className="header">
          <div className="header-inner">
            <div className="logo">
              <span className="logo-icon">\u26A1</span>
              <span className="logo-text">ATHENA</span>
            </div>
            <p className="tagline">Autonomous Multi-Agent Market Intelligence &amp; Strategy</p>
          </div>
        </header>

        <main className="main">

          {/* \u2500\u2500 IDLE: Input form \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */}
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
                    placeholder="e.g. OpenAI, Stripe, DeFi lending protocols\u2026"
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
                    <option value="company">\uD83C\uDFE2 Company</option>
                    <option value="product">\uD83D\uDCE6 Product</option>
                    <option value="market">\uD83C\uDF0D Market</option>
                  </select>
                </div>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={!target.trim() || loading}
                >
                  {loading ? '\u23F3 Starting\u2026' : '\u26A1 Run ATHENA'}
                </button>
              </form>
            </section>
          )}

          {/* \u2500\u2500 RUNNING / DONE: Pipeline view \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */}
          {(appStatus === 'running' || appStatus === 'done') && (
            <>
              {/* Status card */}
              <section className="card">
                <div className="job-header">
                  <div>
                    <h2 className="section-title">
                      {appStatus === 'done' ? '\u2705 Analysis Complete' : '\u26A1 Running Analysis'}
                    </h2>
                    <div className="job-meta">
                      <span className="tag">{type}</span>
                      <span className="job-target">{target}</span>
                      {jobId && <span className="job-id">#{jobId.slice(0, 8)}</span>}
                    </div>
                  </div>
                  {appStatus === 'done' && (
                    <button className="btn btn-secondary" onClick={handleReset}>
                      New Analysis
                    </button>
                  )}
                </div>

                <Timeline currentStage={currentStage} />

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
                    return (
                      <div key={i} className={['log-line', cls].filter(Boolean).join(' ')}>
                        {text}
                      </div>
                    );
                  })}
                  <div ref={logBottomRef} />
                </div>
              </section>

              {/* \u2500\u2500 Results (only when DONE and results loaded) \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */}
              {appStatus === 'done' && results && (
                <>
                  {/* Key Metrics */}
                  <section className="card">
                    <p className="section-title-sm">\uD83D\uDCCA Intelligence Summary</p>
                    <div className="metrics-grid">
                      <div className="metric-item">
                        <div className="metric-value">{results.competitors?.length ?? '\u2014'}</div>
                        <div className="metric-label">Competitors</div>
                      </div>
                      <div className="metric-item">
                        <div className="metric-value">{results.key_trends?.length ?? '\u2014'}</div>
                        <div className="metric-label">Trends</div>
                      </div>
                      <div className="metric-item">
                        <div className="metric-value">
                          {results.presenter_result?.deck_outline.length ?? '\u2014'}
                        </div>
                        <div className="metric-label">Slides</div>
                      </div>
                      <div className="metric-item">
                        <div className="metric-value">
                          {results.presenter_result?.report_markdown
                            ? `${Math.round(results.presenter_result.report_markdown.length / 100) / 10}K`
                            : '\u2014'}
                        </div>
                        <div className="metric-label">Report</div>
                      </div>
                    </div>
                  </section>

                  {/* SWOT Analysis */}
                  {results.swot && (
                    <section className="card">
                      <p className="section-title-sm">\u2694\uFE0F SWOT Analysis</p>
                      <div className="swot-grid">
                        <SWOTQuadrant label="\uD83D\uDCAA Strengths"     items={results.swot.strengths}     kind="s" />
                        <SWOTQuadrant label="\uD83D\uDD27 Weaknesses"    items={results.swot.weaknesses}    kind="w" />
                        <SWOTQuadrant label="\uD83D\uDE80 Opportunities" items={results.swot.opportunities} kind="o" />
                        <SWOTQuadrant label="\u26A0\uFE0F Threats"       items={results.swot.threats}       kind="t" />
                      </div>
                    </section>
                  )}

                  {/* Competitors & Trends */}
                  {((results.competitors?.length ?? 0) > 0 || (results.key_trends?.length ?? 0) > 0) && (
                    <section className="card">
                      <div className="intel-row">
                        {results.competitors && results.competitors.length > 0 && (
                          <div className="intel-col">
                            <p className="section-title-sm">\uD83C\uDFE2 Identified Competitors</p>
                            <div className="intel-chips">
                              {results.competitors.map((c, i) => (
                                <span key={i} className="chip">{c}</span>
                              ))}
                            </div>
                          </div>
                        )}
                        {results.key_trends && results.key_trends.length > 0 && (
                          <div className="intel-col">
                            <p className="section-title-sm">\uD83D\uDCC8 Key Market Trends</p>
                            <ul className="intel-list">
                              {results.key_trends.map((t, i) => (
                                <li key={i}>{t}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    </section>
                  )}

                  {/* GTM Value Proposition */}
                  {results.gtm?.value_proposition && (
                    <section className="card gtm-highlight">
                      <p className="section-title-sm">\uD83C\uDFAF Value Proposition</p>
                      <blockquote className="gtm-vp">
                        {results.gtm.value_proposition}
                      </blockquote>
                      {results.gtm.positioning && (
                        <p className="gtm-positioning">
                          <strong>Recommended Positioning:</strong> {results.gtm.positioning}
                        </p>
                      )}
                    </section>
                  )}

                  {/* Markdown report */}
                  {results.presenter_result && (
                    <section className="card">
                      <div className="results-header">
                        <p className="section-title-sm">\uD83D\uDCC4 Market Intelligence Report</p>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          {copyHint && <span className="copy-hint">Copied!</span>}
                          <button className="btn btn-ghost" onClick={handleCopy}>Copy</button>
                          {results.presenter_result.report_url && (
                            <a
                              href={results.presenter_result.report_url}
                              target="_blank"
                              rel="noreferrer"
                              className="btn btn-ghost"
                            >
                              Download
                            </a>
                          )}
                        </div>
                      </div>
                      <textarea
                        className="report-area"
                        readOnly
                        value={results.presenter_result.report_markdown}
                        spellCheck={false}
                      />
                    </section>
                  )}

                  {/* Deck outline */}
                  {results.presenter_result && results.presenter_result.deck_outline.length > 0 && (
                    <section className="card">
                      <p className="section-title-sm">
                        \uD83C\uDFAF Deck Outline &nbsp;
                        <span style={{
                          opacity: 0.5, fontWeight: 400,
                          textTransform: 'none', letterSpacing: 0,
                        }}>
                          ({results.presenter_result.deck_outline.length} slides)
                        </span>
                      </p>
                      <div className="deck-grid">
                        {results.presenter_result.deck_outline.map((slide: DeckSlide) => (
                          <SlideCard key={slide.slide_number} slide={slide} />
                        ))}
                      </div>
                    </section>
                  )}
                </>
              )}
            </>
          )}

          {/* \u2500\u2500 ERROR \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500 */}
          {appStatus === 'error' && (
            <section className="card error-card">
              <h2 className="section-title">\u274C Analysis Failed</h2>
              <pre className="error-msg">{errorMsg}</pre>
              <button className="btn btn-secondary" onClick={handleReset}>
                Try Again
              </button>
            </section>
          )}

        </main>

        <footer className="footer">
          ATHENA \u00B7 Built for Complete AI Hackathon \u00B7 Powered by Deploy.AI
        </footer>
      </div>
    </>
  );
}
