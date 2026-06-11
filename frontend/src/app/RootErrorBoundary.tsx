import { Component, type ReactNode } from "react";
import { captureException } from "@/lib/sentry";

interface State {
  hasError: boolean;
}

/** Top-level boundary: reports uncaught render errors to Sentry (if enabled). */
export class RootErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error): void {
    void captureException(error);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
          <h1 className="text-xl font-semibold text-text">Something went wrong</h1>
          <p className="text-muted">An unexpected error occurred. Try reloading the page.</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-[10px] bg-accent px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
          >
            Reload
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
