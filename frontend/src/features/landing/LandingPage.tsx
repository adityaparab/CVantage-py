import { Link } from "react-router-dom";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function LandingPage() {
  useDocumentTitle("");
  return (
    <div className="mx-auto max-w-4xl px-4 py-20 text-center">
      <span className="bg-gradient-brand bg-clip-text text-sm font-semibold text-transparent">
        AI-POWERED RESUME ANALYSIS
      </span>
      <h1 className="mt-3 text-4xl font-bold text-text sm:text-5xl">
        Tailor your resume to every job
      </h1>
      <p className="mx-auto mt-4 max-w-2xl text-lg text-muted">
        Upload or build a resume, paste a job description, and get scored analysis, concrete
        suggestions, and interview prep — in minutes.
      </p>
      <div className="mt-8 flex justify-center gap-3">
        <Link
          to="/register"
          className="rounded-[10px] bg-accent px-6 py-3 text-sm font-medium text-white hover:opacity-90"
        >
          Get started
        </Link>
        <Link
          to="/login"
          className="rounded-[10px] border border-border px-6 py-3 text-sm font-medium text-text hover:bg-accent-soft"
        >
          Log in
        </Link>
      </div>
    </div>
  );
}
