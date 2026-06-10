import { useId, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

export function Tabs({ items, defaultTab }: { items: TabItem[]; defaultTab?: string }) {
  const [active, setActive] = useState(defaultTab ?? items[0]?.id);
  const baseId = useId();

  return (
    <div>
      <div role="tablist" aria-label="Tabs" className="flex gap-1 border-b border-border">
        {items.map((item) => {
          const selected = item.id === active;
          return (
            <button
              key={item.id}
              role="tab"
              id={`${baseId}-tab-${item.id}`}
              aria-selected={selected}
              aria-controls={`${baseId}-panel-${item.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(item.id)}
              className={cn(
                "-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent",
                selected
                  ? "border-accent text-accent-text"
                  : "border-transparent text-muted hover:text-text",
              )}
            >
              {item.label}
            </button>
          );
        })}
      </div>
      {items.map((item) => (
        <div
          key={item.id}
          role="tabpanel"
          id={`${baseId}-panel-${item.id}`}
          aria-labelledby={`${baseId}-tab-${item.id}`}
          hidden={item.id !== active}
          className="py-4"
        >
          {item.id === active && item.content}
        </div>
      ))}
    </div>
  );
}

export type StepStatus = "pending" | "in_progress" | "completed" | "failed";

export interface ProgressStep {
  label: string;
  status: StepStatus;
}

const STEP_STYLES: Record<StepStatus, string> = {
  pending: "border-border bg-card text-muted",
  in_progress: "border-accent bg-accent-soft text-accent-text animate-pulse",
  completed: "border-success bg-success-bg text-success",
  failed: "border-danger bg-danger-bg text-danger",
};

const STEP_GLYPH: Record<StepStatus, string> = {
  pending: "○",
  in_progress: "…",
  completed: "✓",
  failed: "✕",
};

export function ProgressSteps({ steps }: { steps: ProgressStep[] }) {
  return (
    <ol className="flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-2">
      {steps.map((step, index) => (
        <li key={step.label} className="flex flex-1 items-center gap-3">
          <span
            className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-full border text-sm font-semibold",
              STEP_STYLES[step.status],
            )}
            aria-hidden="true"
          >
            {STEP_GLYPH[step.status]}
          </span>
          <span className="text-sm font-medium text-text">
            {step.label}
            <span className="sr-only"> — {step.status.replace("_", " ")}</span>
          </span>
          {index < steps.length - 1 && (
            <span className="hidden h-px flex-1 bg-border sm:block" aria-hidden="true" />
          )}
        </li>
      ))}
    </ol>
  );
}
