import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import { getResume, updateResume, type ResumeDetail } from "@/api/resumes";
import { Skeleton, useToast } from "@/components/ui";
import { EditableText } from "@/features/resume/EditableText";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

type Json = Record<string, unknown>;

function setDeep(obj: Json, path: string[], value: string): Json {
  const [head, ...rest] = path;
  const child = (obj[head] as Json | undefined) ?? {};
  return { ...obj, [head]: rest.length === 0 ? value : setDeep(child, rest, value) };
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-border py-5">
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-muted">{title}</h2>
      {children}
    </section>
  );
}

export function ResumeViewPage() {
  const { id = "" } = useParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const resume = useQuery({ queryKey: queryKeys.resumes.detail(id), queryFn: () => getResume(id) });
  useDocumentTitle(resume.data?.name ?? "Resume");

  const mutation = useMutation({
    mutationFn: (json_resume: Json) => updateResume(id, { json_resume }),
    onSuccess: (data: ResumeDetail) => queryClient.setQueryData(queryKeys.resumes.detail(id), data),
    onError: (e) => {
      const err = toApiError(e);
      if (err.statusCode === 409) {
        toast("This resume changed elsewhere — reloading the latest version.", "warn");
        void queryClient.invalidateQueries({ queryKey: queryKeys.resumes.detail(id) });
      } else {
        toast(err.message, "danger");
      }
    },
  });

  async function saveField(path: string[], value: string) {
    const current = (resume.data?.json_resume ?? {}) as Json;
    try {
      await mutation.mutateAsync(setDeep(current, path, value));
    } catch {
      // Surfaced by the mutation's onError (toast + reload); swallow so the
      // inline editor closes rather than rejecting up to the field component.
    }
  }

  if (resume.isLoading) return <Skeleton className="h-64 w-full" />;
  if (resume.isError || !resume.data) {
    return <p className="text-danger">Could not load this resume.</p>;
  }

  const jr = resume.data.json_resume as Json;
  const basics = (jr.basics as Json | undefined) ?? {};
  const work = (jr.work as Json[] | undefined) ?? [];
  const education = (jr.education as Json[] | undefined) ?? [];
  const skills = (jr.skills as Json[] | undefined) ?? [];
  const projects = (jr.projects as Json[] | undefined) ?? [];

  return (
    <article className="mx-auto max-w-3xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-text">{resume.data.name}</h1>
        <Link
          to={`/analyses/new/${id}`}
          className="rounded-[10px] bg-accent px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
        >
          Analyze resume
        </Link>
      </div>

      <header className="mt-4">
        <div className="text-xl font-semibold">
          <EditableText
            label="Name"
            value={asString(basics.name)}
            placeholder="Your name"
            onSave={(v) => saveField(["basics", "name"], v)}
          />
        </div>
        <div className="mt-1 text-muted">
          <EditableText
            label="Headline"
            value={asString(basics.label)}
            placeholder="Headline"
            onSave={(v) => saveField(["basics", "label"], v)}
          />
        </div>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted">
          <EditableText
            label="Email"
            value={asString(basics.email)}
            placeholder="email"
            onSave={(v) => saveField(["basics", "email"], v)}
          />
          <EditableText
            label="Phone"
            value={asString(basics.phone)}
            placeholder="phone"
            onSave={(v) => saveField(["basics", "phone"], v)}
          />
        </div>
      </header>

      <Section title="Summary">
        <EditableText
          label="Summary"
          multiline
          value={asString(basics.summary)}
          placeholder="Add a professional summary"
          onSave={(v) => saveField(["basics", "summary"], v)}
        />
      </Section>

      {work.length > 0 && (
        <Section title="Work">
          <ul className="flex flex-col gap-3">
            {work.map((w, i) => (
              <li key={i}>
                <p className="font-medium text-text">
                  {asString(w.position)} {w.name ? `· ${asString(w.name)}` : ""}
                </p>
                <p className="text-sm text-muted">
                  {asString(w.startDate)}
                  {w.endDate ? ` – ${asString(w.endDate)}` : ""}
                </p>
                {w.summary ? <p className="mt-1 text-sm">{asString(w.summary)}</p> : null}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {education.length > 0 && (
        <Section title="Education">
          <ul className="flex flex-col gap-2">
            {education.map((e, i) => (
              <li key={i} className="text-sm">
                <span className="font-medium text-text">{asString(e.institution)}</span>
                {e.area ? ` — ${asString(e.area)}` : ""}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {skills.length > 0 && (
        <Section title="Skills">
          <div className="flex flex-wrap gap-2">
            {skills.map((s, i) => (
              <span
                key={i}
                className="rounded-full bg-accent-soft px-3 py-1 text-sm text-accent-text"
              >
                {asString(s.name)}
              </span>
            ))}
          </div>
        </Section>
      )}

      {projects.length > 0 && (
        <Section title="Projects">
          <ul className="flex flex-col gap-2">
            {projects.map((p, i) => (
              <li key={i} className="text-sm">
                <span className="font-medium text-text">{asString(p.name)}</span>
                {p.description ? ` — ${asString(p.description)}` : ""}
              </li>
            ))}
          </ul>
        </Section>
      )}

      <p className="mt-6 text-sm text-muted">
        Need to edit other sections?{" "}
        <Link to="/resumes/new" className="text-accent-text">
          Open the full editor
        </Link>
        .
      </p>
    </article>
  );
}
