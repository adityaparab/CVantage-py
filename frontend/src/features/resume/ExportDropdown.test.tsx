import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { ExportDropdown } from "@/features/resume/ExportDropdown";

// Mock the API so the test exercises the dropdown + download wiring without
// axios/jsdom blob plumbing (whose behavior varies across Node versions/CI).
const { exportResume } = vi.hoisted(() => ({
  exportResume: vi.fn(async () => new Blob(["%PDF"], { type: "application/pdf" })),
}));
vi.mock("@/api/resumes", () => ({ exportResume }));

beforeEach(() => {
  exportResume.mockClear();
  // jsdom lacks these blob-URL helpers.
  URL.createObjectURL = vi.fn(() => "blob:mock");
  URL.revokeObjectURL = vi.fn();
});

function renderDropdown() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <ExportDropdown resumeId="r1" name="Backend Resume" />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ExportDropdown", () => {
  it("requests the chosen format and triggers a download", async () => {
    const user = userEvent.setup();
    renderDropdown();

    await user.click(screen.getByRole("button", { name: /Download/ }));
    await user.click(screen.getByRole("menuitem", { name: "Download PDF" }));

    await waitFor(() => expect(exportResume).toHaveBeenCalledWith("r1", "pdf"));
    await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled());
  });

  it("offers both PDF and DOCX", async () => {
    const user = userEvent.setup();
    renderDropdown();
    await user.click(screen.getByRole("button", { name: /Download/ }));
    expect(screen.getByRole("menuitem", { name: "Download PDF" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Download DOCX" })).toBeInTheDocument();
  });
});
