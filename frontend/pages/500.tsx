import Head from 'next/head';
import Link from 'next/link';

/**
 * Custom 500 page for ATHENA.
 * Next.js uses this file for unhandled server-side errors in production.
 * For client-side rendering errors, the ErrorBoundary in _app.tsx takes over.
 */
export default function Custom500() {
  return (
    <>
      <Head>
        <title>500 — Server Error | ATHENA</title>
        <meta name="description" content="The ATHENA intelligence pipeline encountered an unexpected server error." />
      </Head>

      <main
        style={{
          minHeight: '100vh',
          background: '#080d1a',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#e2e8f0',
          fontFamily: 'Inter, system-ui, sans-serif',
          padding: '2rem',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: '4rem', marginBottom: '1.5rem', lineHeight: 1 }}>&#x26A0;&#xFE0F;</div>

        <h1
          style={{
            fontSize: '1.5rem',
            fontWeight: 700,
            color: '#ef4444',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            margin: '0 0 0.5rem',
          }}
        >
          500 — Server Error
        </h1>

        <p
          style={{
            color: '#64748b',
            marginBottom: '2.5rem',
            maxWidth: '420px',
            lineHeight: 1.6,
          }}
        >
          The ATHENA intelligence pipeline encountered an unexpected error.
          Please try again in a moment. If the issue persists, check the
          backend health endpoint at{' '}
          <code
            style={{
              background: '#1e293b',
              padding: '0.1rem 0.4rem',
              borderRadius: '4px',
              fontSize: '0.85em',
              color: '#94a3b8',
            }}
          >
            /api/v1/health
          </code>
          .
        </p>

        <Link
          href="/"
          style={{
            background: '#3b82f6',
            color: '#fff',
            padding: '0.75rem 2rem',
            borderRadius: '8px',
            textDecoration: 'none',
            fontWeight: 600,
            fontSize: '0.95rem',
            display: 'inline-block',
          }}
        >
          ← Return to Base
        </Link>
      </main>
    </>
  );
}
