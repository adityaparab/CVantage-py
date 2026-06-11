import { useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { toApiError } from "@/api/errors";
import { uploadResume, validateUploadFile } from "@/api/upload";
import { Button } from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

type Status = "idle" | "uploading" | "error";

export function UploadPage() {
  useDocumentTitle("Upload resume");
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string>();
  const [dragging, setDragging] = useState(false);

  async function handleFile(file: File) {
    const validationError = validateUploadFile(file);
    if (validationError) {
      setError(validationError);
      setStatus("error");
      return;
    }
    setError(undefined);
    setStatus("uploading");
    setProgress(0);
    try {
      const resume = await uploadResume(file, setProgress);
      navigate(`/resumes/${resume.id}/review`);
    } catch (e) {
      setError(toApiError(e).message);
      setStatus("error");
    }
  }

  function onDrop(event: DragEvent<HTMLButtonElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) void handleFile(file);
  }

  return (
    <div className="mx-auto max-w-xl">
      <h1 className="text-2xl font-bold text-text">Upload your resume</h1>
      <p className="mt-1 text-muted">We’ll structure it with AI so you can review and edit.</p>

      {status === "uploading" ? (
        <div className="mt-8 rounded-card border border-border p-8 text-center">
          <p className="text-sm font-medium text-text">Uploading… {progress}%</p>
          <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-border">
            <div
              className="h-full bg-accent transition-all"
              style={{ width: `${progress}%` }}
              role="progressbar"
              aria-valuenow={progress}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          {progress === 100 && (
            <p className="mt-3 text-sm text-muted">AI is processing your resume…</p>
          )}
        </div>
      ) : (
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          className={`mt-8 flex w-full flex-col items-center gap-2 rounded-card border-2 border-dashed p-12 text-center transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
            dragging ? "border-accent bg-accent-soft" : "border-border hover:bg-accent-soft/40"
          }`}
        >
          <span className="text-base font-medium text-text">
            Drag & drop a file, or click to browse
          </span>
          <span className="text-sm text-muted">PDF, DOC, or DOCX · up to 10 MB</span>
        </button>
      )}

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.doc,.docx"
        className="sr-only"
        aria-label="Choose a resume file"
        onChange={(e) => {
          const file = e.target.files?.[0];
          if (file) void handleFile(file);
          e.target.value = "";
        }}
      />

      {status === "error" && error && (
        <div className="mt-4 flex items-center justify-between gap-3 rounded-md bg-danger-bg px-4 py-3 text-sm text-danger">
          <span role="alert">{error}</span>
          <Button size="sm" variant="secondary" onClick={() => inputRef.current?.click()}>
            Try again
          </Button>
        </div>
      )}
    </div>
  );
}
