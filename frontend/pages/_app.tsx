import React from 'react';
import type { AppProps } from 'next/app';
import '../styles/globals.css';

// ── Error Boundary ─────────────────────────────────────────────────────────────
// Catches unhandled render errors so the whole page doesn't go blank.
interface EBState { hasError: boolean; error: Error | null }

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, EBState> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): EBState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('[ATHENA ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          minHeight: '100vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          background: '#080d1a', color: '#f1f5f9',
          gap: '1rem', padding: '2rem',
          fontFamily: 'Inter, -apple-system, BlinkMacSystemFont, sans-serif',
        }}>
          <span style={{ fontSize: '2.5rem' }}>⚡</span>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700 }}>
            ATHENA encountered an error
          </h2>
          <pre style={{
            background: '#0f1729', border: '1px solid #1e3a5f',
            borderRadius: '8px', padding: '1rem',
            fontSize: '0.78rem', color: '#fca5a5',
            maxWidth: '640px', overflowX: 'auto', whiteSpace: 'pre-wrap',
          }}>
            {this.state.error?.message}
          </pre>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              background: '#3b82f6', color: 'white', border: 'none',
              borderRadius: '8px', padding: '0.6rem 1.4rem',
              cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem',
            }}
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// ── App ──────────────────────────────────────────────────────────────────────
export default function App({ Component, pageProps }: AppProps) {
  return (
    <ErrorBoundary>
      <Component {...pageProps} />
    </ErrorBoundary>
  );
}
