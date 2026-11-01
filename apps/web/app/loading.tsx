export default function Loading() {
  return <main id="main-content" className="library-page loading-state" aria-busy="true" aria-label="Loading research workspace"><div className="skeleton skeleton-title" /><div className="skeleton skeleton-subtitle" /><div className="skeleton skeleton-control" />{[0, 1, 2].map((n) => <div className="skeleton skeleton-row" key={n} />)}<span className="sr-only">Loading reports…</span></main>;
}
