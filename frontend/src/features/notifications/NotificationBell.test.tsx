import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { NotificationBell } from "@/features/notifications/NotificationBell";
import { server } from "@/test/server";

const notif = {
  id: "n1",
  type: "analysis_completed",
  analysis_id: "a7",
  title: "Analysis Complete",
  body: "Your analysis finished.",
  created_at: "2026-06-10T10:00:00Z",
};

function renderBell() {
  const router = createMemoryRouter(
    [
      { path: "/", element: <NotificationBell /> },
      { path: "/analyses/:id", element: <p>Analysis a7</p> },
    ],
    { initialEntries: ["/"] },
  );
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("NotificationBell", () => {
  it("shows the active count and routes to the analysis on click", async () => {
    server.use(
      http.get("*/api/v1/notifications", () => HttpResponse.json({ items: [notif], total: 1 })),
    );
    const user = userEvent.setup();
    renderBell();

    expect(await screen.findByLabelText("Notifications (1 active)")).toBeInTheDocument();
    await user.click(screen.getByLabelText("Notifications (1 active)"));
    await user.click(screen.getByRole("button", { name: /Analysis Complete/ }));
    expect(await screen.findByText("Analysis a7")).toBeInTheDocument();
  });

  it("clears a notification", async () => {
    let cleared = false;
    server.use(
      http.get("*/api/v1/notifications", () =>
        HttpResponse.json({ items: cleared ? [] : [notif], total: cleared ? 0 : 1 }),
      ),
      http.post("*/api/v1/notifications/n1/clear", () => {
        cleared = true;
        return new HttpResponse(null, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderBell();

    await user.click(await screen.findByLabelText("Notifications (1 active)"));
    await user.click(screen.getByRole("button", { name: "Clear notification" }));
    await waitFor(() => expect(screen.getByText("No notifications")).toBeInTheDocument());
  });
});
