import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { applySuggestion, dismissSuggestion, getAnalysis } from "@/api/analyses";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import { getResume } from "@/api/resumes";
import { Badge, Button, Skeleton, Tooltip, useToast } from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

type Json = Record<string, unknown>;

function ResumePreview({ jr }: { jr: Json }) {
  const basics = (jr.basics as Json | undefined) ?? {};
  const work = (jr.work as Json[] | undefined) ?? [];
  const skills = (jr.skills as Json[] | undefined) ?? [];
  const str = (v: unknown) => (typeof v === "string" ? v : "");
  return (
    <div className="text-sm">
      <p className="text-lg font-semibold text-text">{str(basics.name) || "Your resume"}</p>
      <p className="text-muted">{str(basics.label)}</p>
      {basics.summary ? <p className="mt-2 text-text">{str(basics.summary)}</p> : null}
      {work.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold uppercase text-muted">Work</p>
          {work.map((w, i) => (
            <p key={i} className="mt-1 text-text">
              {str(w.position)} {w.name ? `· ${str(w.name)}` : ""}
            </p>
          ))}
        </div>
      )}
      {skills.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5">
          {skills.map((s, i) => (
            <Badge key={i} tone="accent">
              {str(s.name)}
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}

export function ApplySuggestionsPage() {
  const { id = "" } = useParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  useDocumentTitle("Apply suggestions");

  const analysis = useQuery({
    queryKey: queryKeys.analyses.detail(id),
    queryFn: () => getAnalysis(id),
  });
  const resumeId = analysis.data?.resume_id ?? "";
  const resume = useQuery({
    queryKey: queryKeys.resumes.detail(resumeId),
    queryFn: () => getResume(resumeId),
    enabled: Boolean(resumeId),
  });

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.analyses.detail(id) });
    void queryClient.invalidateQueries({ queryKey: queryKeys.resumes.detail(resumeId) });
  }

  const apply = useMutation({
    mutationFn: (sid: string) => applySuggestion(id, sid),
    onSuccess: () => {
      toast("Suggestion applied to your resume.", "success");
      refresh();
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  const dismiss = useMutation({
    mutationFn: (sid: string) => dismissSuggestion(id, sid),
    onSuccess: refresh,
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  if (analysis.isLoading) return <Skeleton className="h-64 w-full" />;
  if (analysis.isError || !analysis.data?.result) {
    return <p className="text-danger">No suggestions available for this analysis.</p>;
  }

  const suggestions = analysis.data.result.suggestions.filter((s) => !s.dismissed);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-text">Apply suggestions</h1>
        <div className="flex items-center gap-2">
          <Tooltip label="Export ships in #9.4">
            <Button variant="secondary" disabled>
              Download ▾
            </Button>
          </Tooltip>
          <Link to={`/analyses/${id}`} className="text-sm text-accent-text">
            Back to results
          </Link>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="rounded-card border border-border bg-card p-6">
          <h2 className="mb-3 text-sm font-semibold uppercase text-muted">Your resume</h2>
          {resume.data ? (
            <ResumePreview jr={resume.data.json_resume as Json} />
          ) : (
            <Skeleton className="h-40 w-full" />
          )}
        </section>

        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase text-muted">Suggestions</h2>
          {suggestions.length === 0 ? (
            <p className="text-sm text-muted">No suggestions left to apply.</p>
          ) : (
            <ul className="flex flex-col gap-3">
              {suggestions.map((s) => (
                <li key={s.suggestion_id} className="rounded-card border border-border p-4">
                  <p className="font-medium text-text">{s.title}</p>
                  <p className="mt-1 text-sm text-muted">{s.description}</p>
                  {s.proposed_value && (
                    <p className="mt-2 rounded-md bg-accent-soft px-3 py-2 text-sm text-accent-text">
                      {s.proposed_value}
                    </p>
                  )}
                  <div className="mt-3 flex gap-2">
                    {s.applied ? (
                      <Badge tone="success">Applied</Badge>
                    ) : (
                      <>
                        <Button
                          size="sm"
                          loading={apply.isPending && apply.variables === s.suggestion_id}
                          onClick={() => apply.mutate(s.suggestion_id)}
                        >
                          Apply
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => dismiss.mutate(s.suggestion_id)}
                        >
                          Dismiss
                        </Button>
                      </>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
