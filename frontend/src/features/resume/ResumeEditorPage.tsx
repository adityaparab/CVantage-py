import { useEffect, useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { useNavigate } from "react-router-dom";
import { toApiError } from "@/api/errors";
import { saveNewResume } from "@/api/resumes";
import { Button, Input, useToast } from "@/components/ui";
import { emptyResumeForm, toJsonResume, type ResumeForm } from "@/features/resume/jsonResume";
import { RESUME_SECTIONS } from "@/features/resume/sections";
import { useUnsavedChangesGuard } from "@/lib/forms";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function ResumeEditorPage() {
  useDocumentTitle("New resume");
  const navigate = useNavigate();
  const { toast } = useToast();
  const [active, setActive] = useState<string>("basics");
  const [saveError, setSaveError] = useState<string>();
  const [savedId, setSavedId] = useState<string>();

  const methods = useForm<ResumeForm>({ defaultValues: emptyResumeForm() });
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty, isSubmitting },
  } = methods;

  // Guard goes off once a save succeeds, so the effect below can navigate freely.
  useUnsavedChangesGuard(isDirty && savedId === undefined);

  useEffect(() => {
    if (savedId) navigate(`/resumes/${savedId}`);
  }, [savedId, navigate]);

  const onSubmit = handleSubmit(async (values) => {
    setSaveError(undefined);
    try {
      const jsonResume = toJsonResume(values);
      const created = await saveNewResume(values.name.trim(), jsonResume);
      setSavedId(created.id);
    } catch (e) {
      const message = toApiError(e).message;
      setSaveError(message);
      toast(message, "danger");
    }
  });

  const ActiveSection =
    RESUME_SECTIONS.find((s) => s.id === active)?.Component ?? RESUME_SECTIONS[0].Component;

  return (
    <FormProvider {...methods}>
      <form onSubmit={onSubmit}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-bold text-text">Create resume</h1>
          <Button type="submit" loading={isSubmitting}>
            Save resume
          </Button>
        </div>

        <div className="mt-6 max-w-md">
          <Input
            label="Resume name"
            placeholder="e.g. Backend Engineer 2026"
            error={errors.name ? "A resume name is required" : undefined}
            {...register("name", { required: true, minLength: 1 })}
          />
        </div>
        {saveError && (
          <p role="alert" className="mt-2 text-sm text-danger">
            {saveError}
          </p>
        )}

        <div className="mt-8 grid gap-8 lg:grid-cols-[200px_1fr]">
          <nav aria-label="Resume sections" className="flex flex-row flex-wrap gap-1 lg:flex-col">
            {RESUME_SECTIONS.map((section) => (
              <button
                key={section.id}
                type="button"
                onClick={() => setActive(section.id)}
                aria-current={active === section.id ? "true" : undefined}
                className={`rounded-md px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-2 focus-visible:outline-accent ${
                  active === section.id
                    ? "bg-accent-soft text-accent-text"
                    : "text-muted hover:text-text"
                }`}
              >
                {section.label}
              </button>
            ))}
          </nav>

          <section className="rounded-card border border-border bg-card p-6">
            <ActiveSection />
          </section>
        </div>
      </form>
    </FormProvider>
  );
}
