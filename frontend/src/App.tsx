/**
 * Root application shell (issue #64).
 *
 * Routing, providers, and the full UI land in later Phase 7/8 issues; for now
 * this renders a minimal shell that proves the Vite + React + TS pipeline.
 */
export function App() {
  return (
    <main className="app-shell">
      <h1>CVantage</h1>
      <p>AI-powered resume analysis for job seekers.</p>
    </main>
  );
}
