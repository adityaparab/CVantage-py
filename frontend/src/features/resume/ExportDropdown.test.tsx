import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { ExportDropdown } from "@/features/resume/ExportDropdown";
import { server } from "@/test/server";

beforeEach(() => {
  // jsdom lacks these blob-URL helpers; add spies without replacing global URL.
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
    const requested: string[] = [];
    server.use(
      http.get("*/api/v1/resumes/r1/export", ({ request }) => {
        requested.push(new URL(request.url).searchParams.get("format") ?? "");
        return new HttpResponse("%PDF-data", { headers: { "Content-Type": "application/pdf" } });
      }),
    );
    const user = userEvent.setup();
    renderDropdown();

    await user.click(screen.getByRole("button", { name: /Download/ }));
    await user.click(screen.getByRole("menuitem", { name: "Download PDF" }));

    await waitFor(() => expect(requested).toContain("pdf"));
    expect(URL.createObjectURL).toHaveBeenCalled();
  });

  it("offers both PDF and DOCX", async () => {
    const user = userEvent.setup();
    renderDropdown();
    await user.click(screen.getByRole("button", { name: /Download/ }));
    expect(screen.getByRole("menuitem", { name: "Download PDF" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "Download DOCX" })).toBeInTheDocument();
  });
});
