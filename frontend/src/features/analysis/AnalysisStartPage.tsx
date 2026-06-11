import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { createAnalysis, JD_MAX, JD_MIN } from "@/api/analyses";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import { getResume } from "@/api/resumes";
import { Button, Input, Textarea } from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function AnalysisStartPage() {
  useDocumentTitle("New analysis");
  const { resumeId = "" } = useParams();
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [jd, setJd] = useState("");
  const [error, setError] = useState<string>();

  const resume = useQuery({
    queryKey: queryKeys.resumes.detail(resumeId),
    queryFn: () => getResume(resumeId),
  });

  const mutation = useMutation({
    mutationFn: () =>
      createAnalysis({ name: name.trim(), job_description: jd, resume_id: resumeId }),
    onSuccess: (analysis) => navigate(`/analyses/${analysis.id}`),
    onError: (e) => setError(toApiError(e).message),
  });

  const jdValid = jd.length >= JD_MIN && jd.length <= JD_MAX;
  const canStart = name.trim().length > 0 && jdValid && !mutation.isPending;

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold text-text">New analysis</h1>
      <p className="mt-1 text-muted">
        Analyzing{" "}
        <span className="font-medium text-text">{resume.data?.name ?? "your resume"}</span> against
        a job description.
      </p>

      <form
        className="mt-8 flex flex-col gap-4"
        onSubmit={(e) => {
          e.preventDefault();
          setError(undefined);
          if (canStart) mutation.mutate();
        }}
      >
        {error && (
          <p role="alert" className="rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}
        <Input
          label="Analysis name"
          placeholder="e.g. Senior Backend Engineer @ Acme"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={200}
        />
        <div>
          <Textarea
            label="Job description"
            placeholder="Paste the job description…"
            value={jd}
            onChange={(e) => setJd(e.target.value)}
            rows={12}
          />
          <p
            className={`mt-1 text-xs ${jdValid || jd.length === 0 ? "text-muted" : "text-danger"}`}
          >
            {jd.length.toLocaleString()} / {JD_MAX.toLocaleString()} characters (min {JD_MIN})
          </p>
        </div>
        <div className="flex gap-2">
          <Button type="submit" disabled={!canStart} loading={mutation.isPending}>
            Start analysis
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setName("");
              setJd("");
              setError(undefined);
            }}
          >
            Clear
          </Button>
        </div>
      </form>
    </div>
  );
}
