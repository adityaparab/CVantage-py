import { Showcase } from "@/components/ui/Showcase";

/**
 * Root application shell (issues #64/#65).
 *
 * Routing and the real screens land in later Phase 7/8 issues. Until the router
 * (#66) exists, dev renders the UI-kit showcase so the design system can be
 * eyeballed and axe-checked in both themes.
 */
export function App() {
  if (import.meta.env.DEV) {
    return <Showcase />;
  }
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold">CVantage</h1>
      <p className="text-muted">AI-powered resume analysis for job seekers.</p>
    </main>
  );
}
