"use client";

import Link from "next/link";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <main id="main-content" className="page-status" role="alert"><h1>The workspace couldn’t be loaded</h1><p>Your reports haven’t changed. Please try loading this page again.</p><div className="status-actions"><button className="button-secondary" onClick={reset}>Try again</button><Link className="text-link" href="/">Back to the library</Link></div></main>;
}
