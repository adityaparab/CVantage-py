import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { ResumeViewPage } from "@/features/resume/ResumeViewPage";
import { server } from "@/test/server";

function detail(name: string, jr: Record<string, unknown>) {
  return {
    id: "r1",
    name,
    source: "created",
    json_resume: jr,
    analysis_status: "unanalyzed",
    analysis_count: 0,
    created_at: "2026-02-01T12:00:00Z",
    updated_at: "2026-02-01T12:00:00Z",
  };
}

function renderView() {
  const router = createMemoryRouter(
    [
      { path: "/resumes/:id", element: <ResumeViewPage /> },
      { path: "/analyses/new/:id", element: <p>Analysis start</p> },
    ],
    { initialEntries: ["/resumes/r1"] },
  );
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("ResumeViewPage", () => {
  it("renders the resume and an Analyze link", async () => {
    server.use(
      http.get("*/api/v1/resumes/r1", () =>
        HttpResponse.json(detail("My Resume", { basics: { name: "Ada Lovelace" } })),
      ),
    );
    renderView();
    expect(await screen.findByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Analyze resume" })).toHaveAttribute(
      "href",
      "/analyses/new/r1",
    );
  });

  it("edits a field in place and PATCHes the updated json_resume", async () => {
    let patched: { json_resume?: Record<string, unknown> } = {};
    server.use(
      http.get("*/api/v1/resumes/r1", () =>
        HttpResponse.json(detail("My Resume", { basics: { name: "Ada" } })),
      ),
      http.patch("*/api/v1/resumes/r1", async ({ request }) => {
        patched = (await request.json()) as typeof patched;
        return HttpResponse.json(detail("My Resume", patched.json_resume!));
      }),
    );
    const user = userEvent.setup();
    renderView();

    await screen.findByText("Ada");
    await user.click(screen.getByRole("button", { name: "Edit Name" }));
    const input = screen.getByLabelText("Name");
    await user.clear(input);
    await user.type(input, "Grace Hopper");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Grace Hopper")).toBeInTheDocument();
    expect(patched.json_resume).toEqual({ basics: { name: "Grace Hopper" } });
  });

  it("warns and reloads on a 409 version conflict", async () => {
    let attempts = 0;
    server.use(
      http.get("*/api/v1/resumes/r1", () => {
        attempts += 1;
        return HttpResponse.json(
          detail("My Resume", { basics: { name: attempts > 1 ? "Latest" : "Ada" } }),
        );
      }),
      http.patch("*/api/v1/resumes/r1", () =>
        HttpResponse.json({ detail: { message: "Version conflict" } }, { status: 409 }),
      ),
    );
    const user = userEvent.setup();
    renderView();

    await screen.findByText("Ada");
    await user.click(screen.getByRole("button", { name: "Edit Name" }));
    await user.clear(screen.getByLabelText("Name"));
    await user.type(screen.getByLabelText("Name"), "Conflicting");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText("Latest")).toBeInTheDocument());
  });
});
