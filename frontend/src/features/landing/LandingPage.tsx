import { Link } from "react-router-dom";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

const FEATURES = [
  {
    title: "Build or upload",
    body: "Craft a resume with the full json-resume editor, or upload a PDF/DOC/DOCX and let AI structure it for you.",
  },
  {
    title: "Score against any JD",
    body: "Paste a job description and get overall, ATS, and project scores with strengths, gaps, and matching skills.",
  },
  {
    title: "Apply suggestions",
    body: "Accept concrete, field-level improvements with one click — then export a polished PDF or DOCX.",
  },
];

const STEPS = [
  {
    n: "1",
    title: "Add your resume",
    body: "Create one in the editor or upload an existing file.",
  },
  { n: "2", title: "Paste a job description", body: "We compare your resume against the role." },
  {
    n: "3",
    title: "Improve & export",
    body: "Apply suggestions, prep for interviews, and download.",
  },
];

function Hero() {
  return (
    <section className="mx-auto max-w-4xl px-4 py-20 text-center sm:py-28">
      <span className="bg-gradient-brand bg-clip-text text-sm font-semibold tracking-wide text-transparent">
        AI-POWERED RESUME ANALYSIS
      </span>
      <h1 className="mt-3 text-4xl font-bold tracking-tight text-text sm:text-6xl">
        Tailor your resume to every job
      </h1>
      <p className="mx-auto mt-5 max-w-2xl text-lg text-muted">
        Upload or build a resume, paste a job description, and get scored analysis, concrete
        suggestions, and interview prep — in minutes.
      </p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link
          to="/register"
          className="rounded-[10px] bg-accent px-6 py-3 text-sm font-medium text-white hover:opacity-90"
        >
          Get started — it’s free
        </Link>
        <Link
          to="/login"
          className="rounded-[10px] border border-border px-6 py-3 text-sm font-medium text-text hover:bg-accent-soft"
        >
          Log in
        </Link>
      </div>
    </section>
  );
}

export function LandingPage() {
  useDocumentTitle("");
  return (
    <div>
      <Hero />

      <section className="mx-auto max-w-5xl px-4 pb-16">
        <div className="grid gap-6 sm:grid-cols-3">
          {FEATURES.map((f) => (
            <div key={f.title} className="rounded-card border border-border bg-card p-6">
              <h2 className="text-lg font-semibold text-text">{f.title}</h2>
              <p className="mt-2 text-sm text-muted">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="border-t border-border bg-card/40 py-16">
        <div className="mx-auto max-w-5xl px-4">
          <h2 className="text-center text-2xl font-bold text-text">How it works</h2>
          <ol className="mt-8 grid gap-6 sm:grid-cols-3">
            {STEPS.map((s) => (
              <li key={s.n} className="flex flex-col items-center text-center">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-base font-bold text-accent-text">
                  {s.n}
                </span>
                <h3 className="mt-3 font-semibold text-text">{s.title}</h3>
                <p className="mt-1 text-sm text-muted">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-3xl px-4 py-20 text-center">
        <h2 className="text-3xl font-bold text-text">Ready to land more interviews?</h2>
        <p className="mt-3 text-muted">Create your first analysis in minutes.</p>
        <Link
          to="/register"
          className="mt-6 inline-block rounded-[10px] bg-accent px-6 py-3 text-sm font-medium text-white hover:opacity-90"
        >
          Get started
        </Link>
      </section>

      <footer className="border-t border-border py-8 text-center text-sm text-muted">
        © 2026 CVantage. AI-powered resume analysis.
      </footer>
    </div>
  );
}
