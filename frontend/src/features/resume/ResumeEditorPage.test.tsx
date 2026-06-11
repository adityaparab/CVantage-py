import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ToastProvider } from "@/components/ui";
import { ResumeEditorPage } from "@/features/resume/ResumeEditorPage";
import { server } from "@/test/server";

function renderEditor() {
  const router = createMemoryRouter(
    [
      { path: "/resumes/new", element: <ResumeEditorPage /> },
      { path: "/resumes/:id", element: <p>Resume view</p> },
    ],
    { initialEntries: ["/resumes/new"] },
  );
  return render(
    <ToastProvider>
      <RouterProvider router={router} />
    </ToastProvider>,
  );
}

describe("ResumeEditorPage", () => {
  it("renders section navigation and switches sections", async () => {
    const user = userEvent.setup();
    renderEditor();
    expect(screen.getByLabelText("Full name")).toBeInTheDocument(); // basics section
    await user.click(screen.getByRole("button", { name: "Skills" }));
    expect(screen.getByRole("button", { name: "Add skill" })).toBeInTheDocument();
  });

  it("saves a pruned json-resume and navigates to the view", async () => {
    let captured: { name?: string; json_resume?: Record<string, unknown> } = {};
    server.use(
      http.post("*/api/v1/resumes", async ({ request }) => {
        captured = (await request.json()) as typeof captured;
        return HttpResponse.json({ id: "r42" }, { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderEditor();

    await user.type(screen.getByLabelText("Resume name"), "Backend Engineer");
    await user.type(screen.getByLabelText("Full name"), "Ada Lovelace");
    await user.click(screen.getByRole("button", { name: "Save resume" }));

    expect(await screen.findByText("Resume view")).toBeInTheDocument();
    expect(captured.name).toBe("Backend Engineer");
    // Placeholders pruned: only the filled basics.name survives.
    expect(captured.json_resume).toEqual({ basics: { name: "Ada Lovelace" } });
  });

  it("blocks saving without a resume name", async () => {
    const user = userEvent.setup();
    renderEditor();
    await user.type(screen.getByLabelText("Full name"), "Ada");
    await user.click(screen.getByRole("button", { name: "Save resume" }));
    expect(await screen.findByText("A resume name is required")).toBeInTheDocument();
  });
});
