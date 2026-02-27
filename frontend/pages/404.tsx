import Head from 'next/head';
import Link from 'next/link';

/**
 * Custom 404 page for ATHENA.
 * Next.js uses this file for all unmatched routes in production.
 */
export default function Custom404() {
  return (
    <>
      <Head>
        <title>404 — Not Found | ATHENA</title>
        <meta name="description" content="The page or intelligence report you are looking for could not be found." />
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
        <div style={{ fontSize: '4rem', marginBottom: '1.5rem', lineHeight: 1 }}>&#x1F50D;</div>

        <h1
          style={{
            fontSize: '1.5rem',
            fontWeight: 700,
            color: '#3b82f6',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            margin: '0 0 0.5rem',
          }}
        >
          404 — Not Found
        </h1>

        <p
          style={{
            color: '#64748b',
            marginBottom: '2.5rem',
            maxWidth: '400px',
            lineHeight: 1.6,
          }}
        >
          The intelligence you’re looking for doesn’t exist here — or the analysis
          job has expired (24-hour TTL).
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
          ← Back to ATHENA
        </Link>
      </main>
    </>
  );
}
