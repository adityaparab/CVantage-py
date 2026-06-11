import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import { getResume, reparseResume, type ResumeDetail } from "@/api/resumes";
import { Badge, Button, Skeleton, Spinner, useToast } from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

type Json = Record<string, unknown>;
const str = (v: unknown) => (typeof v === "string" ? v : "");

function ParsedPreview({ jr }: { jr: Json }) {
  const basics = (jr.basics as Json | undefined) ?? {};
  const work = (jr.work as Json[] | undefined) ?? [];
  const education = (jr.education as Json[] | undefined) ?? [];
  const skills = (jr.skills as Json[] | undefined) ?? [];
  return (
    <div className="flex flex-col gap-3 text-sm">
      <div>
        <p className="text-lg font-semibold text-text">{str(basics.name) || "(no name parsed)"}</p>
        <p className="text-muted">{str(basics.label)}</p>
        <p className="text-muted">
          {[str(basics.email), str(basics.phone)].filter(Boolean).join(" · ")}
        </p>
      </div>
      {basics.summary ? <p className="text-text">{str(basics.summary)}</p> : null}
      {work.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase text-muted">Experience</p>
          {work.map((w, i) => (
            <p key={i} className="mt-1 text-text">
              {str(w.position)} {w.name ? `· ${str(w.name)}` : ""}
            </p>
          ))}
        </div>
      )}
      {education.length > 0 && (
        <div>
          <p className="text-xs font-semibold uppercase text-muted">Education</p>
          {education.map((e, i) => (
            <p key={i} className="mt-1 text-text">
              {str(e.institution)} {e.area ? `— ${str(e.area)}` : ""}
            </p>
          ))}
        </div>
      )}
      {skills.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
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

const PENDING = ["pending", "processing"];

export function ResumeReviewPage() {
  const { id = "" } = useParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  useDocumentTitle("Review upload");

  const resume = useQuery({
    queryKey: queryKeys.resumes.detail(id),
    queryFn: () => getResume(id),
    // Poll while the AI parse is still running (e.g. after a re-parse).
    refetchInterval: (query) => {
      const status = (query.state.data as ResumeDetail | undefined)?.upload_parse?.status;
      return status && PENDING.includes(status) ? 1500 : false;
    },
  });

  const reparse = useMutation({
    mutationFn: () => reparseResume(id),
    onSuccess: (data) => queryClient.setQueryData(queryKeys.resumes.detail(id), data),
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  if (resume.isLoading) return <Skeleton className="h-64 w-full" />;
  if (resume.isError || !resume.data) {
    return <p className="text-danger">Could not load this resume.</p>;
  }

  const r = resume.data;
  const status = r.upload_parse?.status;

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text">Review your upload</h1>
          <p className="text-muted">{r.name}</p>
        </div>
        {status && (
          <Badge
            tone={status === "completed" ? "success" : status === "failed" ? "danger" : "warn"}
          >
            {status === "completed" ? "Parsed" : status === "failed" ? "Parse failed" : "Parsing…"}
          </Badge>
        )}
      </div>

      {status && PENDING.includes(status) && (
        <div className="flex items-center gap-3 rounded-card border border-border bg-card p-6">
          <Spinner />
          <p className="text-text">Parsing your resume with AI… this updates automatically.</p>
        </div>
      )}

      {status === "failed" && (
        <div className="rounded-card border border-danger/30 bg-danger-bg p-4">
          <p className="text-sm font-medium text-danger">We couldn’t parse this file.</p>
          {r.upload_parse?.error && (
            <p className="mt-1 text-sm text-danger/90">{r.upload_parse.error}</p>
          )}
          <Button
            className="mt-3"
            variant="secondary"
            loading={reparse.isPending}
            onClick={() => reparse.mutate()}
          >
            Try again
          </Button>
        </div>
      )}

      {status !== "failed" && (
        <div className="grid gap-5 lg:grid-cols-2">
          <section className="rounded-card border border-border bg-card p-6">
            <h2 className="mb-3 text-sm font-semibold uppercase text-muted">What we extracted</h2>
            <ParsedPreview jr={r.json_resume as Json} />
          </section>
          <section className="rounded-card border border-border bg-card p-6">
            <h2 className="mb-3 text-sm font-semibold uppercase text-muted">Original text</h2>
            {r.original_text ? (
              <pre className="max-h-96 overflow-auto whitespace-pre-wrap text-xs text-muted">
                {r.original_text}
              </pre>
            ) : (
              <p className="text-sm text-muted">No extracted text available.</p>
            )}
          </section>
        </div>
      )}

      <div className="flex items-center justify-end gap-3">
        <Link
          to={`/resumes/${id}`}
          className="rounded-[10px] bg-accent px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
        >
          Looks good — edit &amp; continue
        </Link>
      </div>
      <p className="text-right text-xs text-muted">
        You can fix any field inline on the resume page.
      </p>
    </div>
  );
}
