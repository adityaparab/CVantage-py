import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { AnalysisDetailPage } from "@/features/analysis/AnalysisDetailPage";
import { server } from "@/test/server";

const steps = [
  { key: "compare_resume_jd", status: "completed", error: null },
  { key: "generate_suggestions", status: "completed", error: null },
  { key: "prepare_interview_questions", status: "completed", error: null },
];

function analysis(overrides: Record<string, unknown>) {
  return {
    id: "a1",
    name: "Senior role",
    resume_id: "r1",
    job_description: "x",
    status: "completed",
    steps,
    result: null,
    token_usage: null,
    error: null,
    created_at: "2026-06-10T10:00:00Z",
    updated_at: "2026-06-10T10:00:00Z",
    ...overrides,
  };
}

function renderDetail() {
  const router = createMemoryRouter([{ path: "/analyses/:id", element: <AnalysisDetailPage /> }], {
    initialEntries: ["/analyses/a1"],
  });
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AnalysisDetailPage", () => {
  it("renders the 3 progress steps and the completed score", async () => {
    server.use(
      http.get("*/api/v1/analyses/a1", () =>
        HttpResponse.json(analysis({ result: { overall_score: 82 } })),
      ),
    );
    renderDetail();
    expect(await screen.findByText("Comparing resume & JD")).toBeInTheDocument();
    expect(screen.getByText("Generating suggestions")).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
  });

  it("shows a retry action for a failed analysis", async () => {
    let retried = false;
    server.use(
      http.get("*/api/v1/analyses/a1", () => {
        if (retried) return HttpResponse.json(analysis({ result: { overall_score: 70 } }));
        return HttpResponse.json(
          analysis({
            status: "failed",
            error: "step failed",
            steps: [
              { key: "compare_resume_jd", status: "completed", error: null },
              { key: "generate_suggestions", status: "failed", error: "boom" },
              { key: "prepare_interview_questions", status: "pending", error: null },
            ],
          }),
        );
      }),
      http.post("*/api/v1/analyses/a1/retry", () => {
        retried = true;
        return HttpResponse.json(analysis({ result: { overall_score: 70 } }));
      }),
    );
    const user = userEvent.setup();
    renderDetail();

    expect(await screen.findByText("Analysis failed")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Retry analysis" }));
    expect(await screen.findByText("70")).toBeInTheDocument();
  });
});
