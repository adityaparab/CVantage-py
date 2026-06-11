import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { AnalysisStartPage } from "@/features/analysis/AnalysisStartPage";
import { server } from "@/test/server";

function renderStart() {
  const router = createMemoryRouter(
    [
      { path: "/analyses/new/:resumeId", element: <AnalysisStartPage /> },
      { path: "/analyses/:id", element: <p>Analysis progress</p> },
    ],
    { initialEntries: ["/analyses/new/r1"] },
  );
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("AnalysisStartPage", () => {
  it("disables start until a name and a long-enough JD are present, then creates", async () => {
    server.use(
      http.get("*/api/v1/resumes/r1", () =>
        HttpResponse.json({ id: "r1", name: "Backend Resume", json_resume: {} }),
      ),
      http.post("*/api/v1/analyses", () => HttpResponse.json({ id: "a9", status: "completed" })),
    );
    const user = userEvent.setup();
    renderStart();

    const start = await screen.findByRole("button", { name: "Start analysis" });
    expect(start).toBeDisabled();

    await user.type(screen.getByLabelText("Analysis name"), "Senior role");
    await user.type(screen.getByLabelText("Job description"), "too short");
    expect(start).toBeDisabled();

    await user.clear(screen.getByLabelText("Job description"));
    await user.type(screen.getByLabelText("Job description"), "x".repeat(40));
    expect(start).toBeEnabled();

    await user.click(start);
    expect(await screen.findByText("Analysis progress")).toBeInTheDocument();
  });

  it("clears both fields", async () => {
    server.use(
      http.get("*/api/v1/resumes/r1", () =>
        HttpResponse.json({ id: "r1", name: "Backend Resume", json_resume: {} }),
      ),
    );
    const user = userEvent.setup();
    renderStart();

    const name = await screen.findByLabelText("Analysis name");
    await user.type(name, "Draft");
    await user.type(screen.getByLabelText("Job description"), "some content");
    await user.click(screen.getByRole("button", { name: "Clear" }));

    expect(name).toHaveValue("");
    expect(screen.getByLabelText("Job description")).toHaveValue("");
  });
});
