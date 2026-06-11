import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { getAnalysis, retryAnalysis, type Analysis } from "@/api/analyses";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import { Badge, Button, ProgressSteps, Skeleton, useToast, type StepStatus } from "@/components/ui";
import { AnalysisResults } from "@/features/analysis/AnalysisResults";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

const STEP_LABELS: Record<string, string> = {
  compare_resume_jd: "Comparing resume & JD",
  generate_suggestions: "Generating suggestions",
  prepare_interview_questions: "Preparing interview questions",
};

const TERMINAL = ["completed", "failed", "cancelled"];

export function AnalysisDetailPage() {
  const { id = "" } = useParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const analysis = useQuery({
    queryKey: queryKeys.analyses.detail(id),
    queryFn: () => getAnalysis(id),
    // Polling fallback so pending/in-progress analyses advance without SSE.
    refetchInterval: (query) => {
      const status = (query.state.data as Analysis | undefined)?.status;
      return status && !TERMINAL.includes(status) ? 1500 : false;
    },
  });

  const retry = useMutation({
    mutationFn: () => retryAnalysis(id),
    onSuccess: (data) => queryClient.setQueryData(queryKeys.analyses.detail(id), data),
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  useDocumentTitle(analysis.data?.name ?? "Analysis");

  if (analysis.isLoading) return <Skeleton className="h-48 w-full" />;
  if (analysis.isError || !analysis.data) {
    return <p className="text-danger">Could not load this analysis.</p>;
  }

  const a = analysis.data;
  const steps = a.steps.map((s) => ({
    label: STEP_LABELS[s.key] ?? s.key,
    status: s.status as StepStatus,
  }));

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-text">{a.name}</h1>
        <Badge
          tone={
            a.status === "completed"
              ? "success"
              : a.status === "failed"
                ? "danger"
                : a.status === "cancelled"
                  ? "neutral"
                  : "warn"
          }
        >
          {a.status.replace("_", " ")}
        </Badge>
      </div>

      <section className="rounded-card border border-border bg-card p-6">
        <ProgressSteps steps={steps} />
      </section>

      {a.status === "failed" && (
        <div className="rounded-card border border-danger/30 bg-danger-bg p-4">
          <p className="text-sm font-medium text-danger">Analysis failed</p>
          {a.error && <p className="mt-1 text-sm text-danger/90">{a.error}</p>}
          <Button
            className="mt-3"
            variant="secondary"
            loading={retry.isPending}
            onClick={() => retry.mutate()}
          >
            Retry analysis
          </Button>
        </div>
      )}

      {a.status === "completed" && a.result && (
        <AnalysisResults
          result={a.result}
          actions={
            <Link
              to={`/analyses/${id}/apply`}
              className="rounded-[10px] bg-accent px-4 py-2 text-sm font-medium text-white hover:opacity-90"
            >
              Apply suggestions
            </Link>
          }
        />
      )}
    </div>
  );
}
