import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormProvider, useForm } from "react-hook-form";
import { describe, expect, it } from "vitest";
import { emptyResumeForm, type ResumeForm } from "@/features/resume/jsonResume";
import {
  AwardsSection,
  CertificatesSection,
  EducationSection,
  InterestsSection,
  LanguagesSection,
  MetaSection,
  ProjectsSection,
  PublicationsSection,
  ReferencesSection,
  VolunteerSection,
  WorkSection,
} from "@/features/resume/sections";

function Harness({ children }: { children: React.ReactNode }) {
  const methods = useForm<ResumeForm>({ defaultValues: emptyResumeForm() });
  return <FormProvider {...methods}>{children}</FormProvider>;
}

const SECTIONS = [
  { Component: WorkSection, add: "Add work experience" },
  { Component: VolunteerSection, add: "Add volunteering" },
  { Component: EducationSection, add: "Add education" },
  { Component: AwardsSection, add: "Add award" },
  { Component: CertificatesSection, add: "Add certificate" },
  { Component: PublicationsSection, add: "Add publication" },
  { Component: LanguagesSection, add: "Add language" },
  { Component: InterestsSection, add: "Add interest" },
  { Component: ReferencesSection, add: "Add reference" },
  { Component: ProjectsSection, add: "Add project" },
];

describe("resume sections", () => {
  it.each(SECTIONS)("renders $add and adds an item", async ({ Component, add }) => {
    const user = userEvent.setup();
    render(
      <Harness>
        <Component />
      </Harness>,
    );
    const addButton = screen.getByRole("button", { name: add });
    await user.click(addButton);
    // Adding an item reveals item controls (Remove + reorder).
    expect(screen.getByRole("button", { name: "Remove" })).toBeInTheDocument();
  });

  it("renders the meta section fields", () => {
    render(
      <Harness>
        <MetaSection />
      </Harness>,
    );
    expect(screen.getByLabelText("Canonical URL")).toBeInTheDocument();
    expect(screen.getByLabelText("Version")).toBeInTheDocument();
  });
});
