import { render } from "@testing-library/react";
import { FormProvider, useForm } from "react-hook-form";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { axe } from "vitest-axe";
import { Badge, Button, EmptyState, ProgressSteps } from "@/components/ui";
import { NotFoundPage } from "@/app/ErrorPages";
import { LandingPage } from "@/features/landing/LandingPage";
import { CheckboxField, SelectField, TextField } from "@/lib/forms";

interface DemoValues {
  email: string;
  role: string;
  agree: boolean;
}

function DemoForm() {
  const methods = useForm<DemoValues>({ defaultValues: { email: "", role: "a", agree: false } });
  return (
    <FormProvider {...methods}>
      <form>
        <TextField<DemoValues> name="email" label="Email" type="email" />
        <SelectField<DemoValues>
          name="role"
          label="Role"
          options={[
            { value: "a", label: "Candidate" },
            { value: "b", label: "Admin" },
          ]}
        />
        <CheckboxField<DemoValues> name="agree" label="I agree" />
        <Button type="submit">Submit</Button>
      </form>
    </FormProvider>
  );
}

describe("accessibility (axe)", () => {
  it("landing page has no violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("the 404 page has no violations", async () => {
    const { container } = render(
      <MemoryRouter>
        <NotFoundPage />
      </MemoryRouter>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });

  it("form controls are labelled with no violations", async () => {
    const { container } = render(<DemoForm />);
    expect(await axe(container)).toHaveNoViolations();
  });

  it("status/feedback components have no violations", async () => {
    const { container } = render(
      <div>
        <Badge tone="success">Completed</Badge>
        <EmptyState title="Nothing here" description="Create one." />
        <ProgressSteps
          steps={[
            { label: "Comparing", status: "completed" },
            { label: "Suggestions", status: "in_progress" },
          ]}
        />
      </div>,
    );
    expect(await axe(container)).toHaveNoViolations();
  });
});
