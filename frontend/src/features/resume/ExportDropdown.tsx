import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toApiError } from "@/api/errors";
import { exportResume } from "@/api/resumes";
import { Button, useToast } from "@/components/ui";

/** Triggers a browser download of a blob. */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ExportDropdown({ resumeId, name }: { resumeId: string; name: string }) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);

  const download = useMutation({
    mutationFn: (format: "pdf" | "docx") => exportResume(resumeId, format),
    onSuccess: (blob, format) => {
      const safe = name.replace(/[^\w-]+/g, "_") || "resume";
      downloadBlob(blob, `${safe}.${format}`);
      setOpen(false);
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  return (
    <div className="relative">
      <Button
        variant="secondary"
        aria-haspopup="menu"
        aria-expanded={open}
        loading={download.isPending}
        onClick={() => setOpen((v) => !v)}
      >
        Download ▾
      </Button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-1 w-40 overflow-hidden rounded-card border border-border bg-card shadow-lg"
        >
          <button
            type="button"
            role="menuitem"
            className="block w-full px-4 py-2 text-left text-sm text-text hover:bg-accent-soft"
            onClick={() => download.mutate("pdf")}
          >
            Download PDF
          </button>
          <button
            type="button"
            role="menuitem"
            className="block w-full px-4 py-2 text-left text-sm text-text hover:bg-accent-soft"
            onClick={() => download.mutate("docx")}
          >
            Download DOCX
          </button>
        </div>
      )}
    </div>
  );
}
