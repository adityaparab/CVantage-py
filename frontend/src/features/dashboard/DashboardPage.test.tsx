import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { server } from "@/test/server";

const resumeRow = {
  id: "r1",
  name: "Backend Engineer Resume",
  source: "created",
  analysis_status: "completed",
  last_analyzed_at: "2026-06-09T08:00:00Z",
  analysis_count: 2,
  created_at: "2026-02-01T12:00:00Z",
};

function renderDashboard(children: ReactNode) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("DashboardPage", () => {
  it("renders stats and the resume table", async () => {
    server.use(
      http.get("*/api/v1/users/me/stats", () =>
        HttpResponse.json({ resumeCount: 1, analysisCount: 2 }),
      ),
      http.get("*/api/v1/resumes", () =>
        HttpResponse.json({ items: [resumeRow], total: 1, skip: 0, limit: 20 }),
      ),
    );
    renderDashboard(<DashboardPage />);

    expect(await screen.findByText("Backend Engineer Resume")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(await screen.findByText("1")).toBeInTheDocument(); // resume count
  });

  it("shows an empty state when there are no resumes", async () => {
    server.use(
      http.get("*/api/v1/users/me/stats", () =>
        HttpResponse.json({ resumeCount: 0, analysisCount: 0 }),
      ),
      http.get("*/api/v1/resumes", () =>
        HttpResponse.json({ items: [], total: 0, skip: 0, limit: 20 }),
      ),
    );
    renderDashboard(<DashboardPage />);
    expect(await screen.findByText("No resumes yet")).toBeInTheDocument();
  });

  it("confirms then optimistically removes a deleted resume", async () => {
    let deleted = false;
    server.use(
      http.get("*/api/v1/users/me/stats", () =>
        HttpResponse.json({ resumeCount: 1, analysisCount: 0 }),
      ),
      http.get("*/api/v1/resumes", () =>
        HttpResponse.json({
          items: deleted ? [] : [resumeRow],
          total: deleted ? 0 : 1,
          skip: 0,
          limit: 20,
        }),
      ),
      http.delete("*/api/v1/resumes/r1", () => {
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const user = userEvent.setup();
    renderDashboard(<DashboardPage />);

    await screen.findByText("Backend Engineer Resume");
    await user.click(screen.getByRole("button", { name: "Delete" }));

    const dialog = await screen.findByRole("dialog", { name: "Delete resume?" });
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(screen.queryByText("Backend Engineer Resume")).not.toBeInTheDocument(),
    );
  });
});
