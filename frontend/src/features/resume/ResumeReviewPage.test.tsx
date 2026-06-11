import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { ResumeReviewPage } from "@/features/resume/ResumeReviewPage";
import { server } from "@/test/server";

function detail(overrides: Record<string, unknown>) {
  return {
    id: "r1",
    name: "Backend Resume",
    source: "uploaded",
    json_resume: {
      basics: { name: "Ada Lovelace", label: "Engineer" },
      skills: [{ name: "python" }],
    },
    analysis_status: "unanalyzed",
    original_text: "Ada Lovelace\nSenior Engineer\nPython, FastAPI",
    upload_parse: {
      status: "completed",
      error: null,
      model_used: "fake",
      started_at: null,
      completed_at: null,
    },
    analysis_count: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderReview() {
  const router = createMemoryRouter(
    [
      { path: "/resumes/:id/review", element: <ResumeReviewPage /> },
      { path: "/resumes/:id", element: <p>Resume page</p> },
    ],
    { initialEntries: ["/resumes/r1/review"] },
  );
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ResumeReviewPage", () => {
  it("shows the parsed result beside the original text", async () => {
    server.use(http.get("*/api/v1/resumes/r1", () => HttpResponse.json(detail({}))));
    renderReview();
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("python")).toBeInTheDocument();
    expect(screen.getByText(/Senior Engineer/)).toBeInTheDocument();
    expect(screen.getByText("Parsed")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /edit & continue/i })).toHaveAttribute(
      "href",
      "/resumes/r1",
    );
  });

  it("offers a re-parse when parsing failed", async () => {
    let attempts = 0;
    server.use(
      http.get("*/api/v1/resumes/r1", () => {
        attempts += 1;
        return HttpResponse.json(
          detail({
            json_resume: {},
            original_text: null,
            upload_parse: { status: "failed", error: "Could not extract text", model_used: null },
          }),
        );
      }),
      http.post("*/api/v1/resumes/r1/reparse", () => HttpResponse.json(detail({}))),
    );
    const user = userEvent.setup();
    renderReview();

    expect(await screen.findByText(/couldn’t parse/i)).toBeInTheDocument();
    expect(screen.getByText("Could not extract text")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(attempts).toBeGreaterThan(0);
  });
});
