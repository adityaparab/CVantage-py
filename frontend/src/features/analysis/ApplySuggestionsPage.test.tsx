import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { ApplySuggestionsPage } from "@/features/analysis/ApplySuggestionsPage";
import { server } from "@/test/server";

function suggestion(id: string, applied: boolean, dismissed: boolean) {
  return {
    suggestion_id: id,
    group: "wording",
    field_ref: "basics.summary",
    title: `Suggestion ${id}`,
    description: "Improve it.",
    proposed_value: "New value",
    applied,
    dismissed,
  };
}

function renderApply() {
  const router = createMemoryRouter(
    [
      { path: "/analyses/:id/apply", element: <ApplySuggestionsPage /> },
      { path: "/analyses/:id", element: <p>Results</p> },
    ],
    { initialEntries: ["/analyses/a1/apply"] },
  );
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ApplySuggestionsPage", () => {
  it("applies a suggestion and reflects the applied state", async () => {
    const state = { applied: false };
    server.use(
      http.get("*/api/v1/analyses/a1", () =>
        HttpResponse.json({
          id: "a1",
          name: "A",
          resume_id: "r1",
          status: "completed",
          steps: [],
          result: { suggestions: [suggestion("s1", state.applied, false)] },
        }),
      ),
      http.get("*/api/v1/resumes/r1", () =>
        HttpResponse.json({ id: "r1", name: "R", json_resume: { basics: { name: "Ada" } } }),
      ),
      http.post("*/api/v1/analyses/a1/suggestions/s1/apply", () => {
        state.applied = true;
        return HttpResponse.json({ status: "ok" });
      }),
    );
    const user = userEvent.setup();
    renderApply();

    expect(await screen.findByText("Suggestion s1")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText("Applied")).toBeInTheDocument();
  });

  it("dismisses a suggestion", async () => {
    const state = { dismissed: false };
    server.use(
      http.get("*/api/v1/analyses/a1", () =>
        HttpResponse.json({
          id: "a1",
          name: "A",
          resume_id: "r1",
          status: "completed",
          steps: [],
          result: { suggestions: [suggestion("s1", false, state.dismissed)] },
        }),
      ),
      http.get("*/api/v1/resumes/r1", () =>
        HttpResponse.json({ id: "r1", name: "R", json_resume: {} }),
      ),
      http.post("*/api/v1/analyses/a1/suggestions/s1/dismiss", () => {
        state.dismissed = true;
        return HttpResponse.json({ status: "ok" });
      }),
    );
    const user = userEvent.setup();
    renderApply();

    await screen.findByText("Suggestion s1");
    await user.click(screen.getByRole("button", { name: "Dismiss" }));
    await waitFor(() =>
      expect(screen.getByText("No suggestions left to apply.")).toBeInTheDocument(),
    );
  });
});
