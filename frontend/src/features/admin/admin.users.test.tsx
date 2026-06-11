import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { AdminUserDetailPage } from "@/features/admin/AdminUserDetailPage";
import { AdminUsersPage } from "@/features/admin/AdminUsersPage";
import { AuthProvider } from "@/lib/auth";
import { server } from "@/test/server";

const adminMe = {
  id: "admin1",
  email: "admin@x.io",
  fullName: "Admin",
  role: "admin",
  emailVerified: true,
  resumeCount: 0,
  analysisCount: 0,
};

function user(id: string, fullName: string) {
  return {
    id,
    fullName,
    email: `${fullName.toLowerCase()}@x.io`,
    role: "candidate",
    status: "active",
    registrationDate: "2026-01-01T00:00:00Z",
    lastActiveAt: null,
    resumeCount: 1,
    analysisCount: 2,
  };
}

function withProviders(node: ReactNode) {
  return (
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <AuthProvider>{node}</AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

describe("AdminUsersPage", () => {
  it("lists users and deactivates one via the confirm modal", async () => {
    let deactivated = false;
    server.use(
      http.get("*/api/v1/users/me", () => HttpResponse.json(adminMe)),
      http.get("*/api/v1/admin/users", () =>
        HttpResponse.json({
          items: deactivated ? [] : [user("u1", "Jane")],
          total: deactivated ? 0 : 1,
          skip: 0,
          limit: 50,
        }),
      ),
      http.post("*/api/v1/admin/users/u1/deactivate", () => {
        deactivated = true;
        return new HttpResponse(null, { status: 200 });
      }),
    );
    const user_ = userEvent.setup();
    render(withProviders(<MemoryRouter>{<AdminUsersPage />}</MemoryRouter>));

    expect(await screen.findByText("Jane")).toBeInTheDocument();
    await user_.click(screen.getByRole("button", { name: "Deactivate" }));
    const dialog = await screen.findByRole("dialog", { name: "Deactivate user?" });
    await user_.click(within(dialog).getByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(screen.queryByText("Jane")).not.toBeInTheDocument());
  });
});

describe("AdminUserDetailPage", () => {
  it("edits the profile and deletes a resume (metadata only)", async () => {
    let patched: { fullName?: string } = {};
    let resumeDeleted = false;
    server.use(
      http.get("*/api/v1/admin/users/u1", () => HttpResponse.json(user("u1", "Jane"))),
      http.get("*/api/v1/admin/users/u1/resumes", () =>
        HttpResponse.json({
          items: resumeDeleted
            ? []
            : [
                {
                  id: "r1",
                  name: "Backend Resume",
                  source: "created",
                  analysisStatus: "completed",
                  analysisCount: 2,
                  createdAt: "2026-01-01T00:00:00Z",
                  lastAnalyzedAt: null,
                },
              ],
        }),
      ),
      http.patch("*/api/v1/admin/users/u1", async ({ request }) => {
        patched = (await request.json()) as typeof patched;
        return HttpResponse.json({ ...user("u1", patched.fullName ?? "Jane") });
      }),
      http.delete("*/api/v1/admin/resumes/r1", () => {
        resumeDeleted = true;
        return new HttpResponse(null, { status: 200 });
      }),
    );
    const router = createMemoryRouter(
      [{ path: "/admin/users/:id", element: <AdminUserDetailPage /> }],
      {
        initialEntries: ["/admin/users/u1"],
      },
    );
    const u = userEvent.setup();
    render(withProviders(<RouterProvider router={router} />));

    const nameInput = await screen.findByLabelText("Full name");
    expect(nameInput).toHaveValue("Jane");
    // No resume content (json_resume / original_text) is rendered — only metadata.
    expect(screen.getByText("Backend Resume")).toBeInTheDocument();

    await u.clear(nameInput);
    await u.type(nameInput, "Jane Doe");
    await u.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(patched.fullName).toBe("Jane Doe"));

    await u.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("dialog", { name: "Delete resume?" });
    await u.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.getByText("This user has no resumes.")).toBeInTheDocument());
  });

  it("resets the password and deactivates the user", async () => {
    let resetCalled = false;
    let status = "active";
    server.use(
      http.get("*/api/v1/admin/users/u1", () =>
        HttpResponse.json({ ...user("u1", "Jane"), status }),
      ),
      http.get("*/api/v1/admin/users/u1/resumes", () => HttpResponse.json({ items: [] })),
      http.post("*/api/v1/admin/users/u1/reset-password", () => {
        resetCalled = true;
        return HttpResponse.json({ status: "ok", method: "reset_email" });
      }),
      http.post("*/api/v1/admin/users/u1/deactivate", () => {
        status = "deactivated";
        return new HttpResponse(null, { status: 200 });
      }),
      http.post("*/api/v1/admin/users/u1/reactivate", () => {
        status = "active";
        return new HttpResponse(null, { status: 200 });
      }),
    );
    const router = createMemoryRouter(
      [{ path: "/admin/users/:id", element: <AdminUserDetailPage /> }],
      { initialEntries: ["/admin/users/u1"] },
    );
    const u = userEvent.setup();
    render(withProviders(<RouterProvider router={router} />));

    await u.click(await screen.findByRole("button", { name: "Reset password" }));
    await waitFor(() => expect(resetCalled).toBe(true));

    await u.click(screen.getByRole("button", { name: "Deactivate" }));
    const reactivate = await screen.findByRole("button", { name: "Reactivate" });
    await u.click(reactivate);
    await waitFor(() =>
      expect(screen.getByRole("button", { name: "Deactivate" })).toBeInTheDocument(),
    );
  });
});

describe("AdminUsersPage search", () => {
  it("issues a debounced, server-driven search", async () => {
    const searches: string[] = [];
    server.use(
      http.get("*/api/v1/users/me", () => HttpResponse.json(adminMe)),
      http.get("*/api/v1/admin/users", ({ request }) => {
        const term = new URL(request.url).searchParams.get("search");
        if (term) searches.push(term);
        return HttpResponse.json({
          items: term === "bob" ? [user("u2", "Bob")] : [user("u1", "Jane")],
          total: 1,
          skip: 0,
          limit: 50,
        });
      }),
    );
    const u = userEvent.setup();
    render(withProviders(<MemoryRouter>{<AdminUsersPage />}</MemoryRouter>));

    await screen.findByText("Jane");
    await u.type(screen.getByLabelText("Search"), "bob");
    await waitFor(() => expect(searches).toContain("bob"));
    expect(await screen.findByText("Bob")).toBeInTheDocument();
  });
});
