import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider, type RouteObject } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { setAccessToken } from "@/api/token";
import { ForgotPasswordPage } from "@/features/auth/ForgotPasswordPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { AuthProvider } from "@/lib/auth";
import { server } from "@/test/server";

afterEach(() => setAccessToken(null));

const anonHandlers = [
  http.get("*/api/v1/users/me", () => new HttpResponse(null, { status: 401 })),
  http.post("*/api/v1/auth/refresh", () => new HttpResponse(null, { status: 401 })),
  http.get("*/api/v1/auth/providers", () => HttpResponse.json({ google: false, linkedin: false })),
];

function renderRoute(initialPath: string, routes: RouteObject[]) {
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] });
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <AuthProvider>
        <RouterProvider router={router} />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  it("logs in and navigates to the destination", async () => {
    server.use(
      ...anonHandlers,
      http.post("*/api/v1/auth/login", () => HttpResponse.json({ accessToken: "tok" })),
    );
    const user = userEvent.setup();
    renderRoute("/login", [
      { path: "/login", element: <LoginPage /> },
      { path: "/dashboard", element: <p>Dashboard reached</p> },
    ]);

    await user.type(await screen.findByLabelText("Email"), "a@b.io");
    await user.type(screen.getByLabelText("Password"), "secret");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Dashboard reached")).toBeInTheDocument();
  });

  it("surfaces a server error message", async () => {
    server.use(
      ...anonHandlers,
      http.post("*/api/v1/auth/login", () =>
        HttpResponse.json({ detail: { message: "Invalid email or password" } }, { status: 401 }),
      ),
    );
    const user = userEvent.setup();
    renderRoute("/login", [{ path: "/login", element: <LoginPage /> }]);

    await user.type(await screen.findByLabelText("Email"), "a@b.io");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByText("Invalid email or password")).toBeInTheDocument();
  });
});

describe("RegisterPage", () => {
  it("shows the password-strength meter as the user types", async () => {
    server.use(...anonHandlers);
    const user = userEvent.setup();
    renderRoute("/register", [{ path: "/register", element: <RegisterPage /> }]);

    await user.type(await screen.findByLabelText("Password"), "StrongPass1");
    expect(screen.getByText(/Password strength: Strong/)).toBeInTheDocument();
  });
});

describe("ForgotPasswordPage", () => {
  it("confirms after submitting without leaking account existence", async () => {
    server.use(
      ...anonHandlers,
      http.post("*/api/v1/auth/forgot-password", () => new HttpResponse(null, { status: 202 })),
    );
    const user = userEvent.setup();
    renderRoute("/forgot-password", [
      { path: "/forgot-password", element: <ForgotPasswordPage /> },
    ]);

    await user.type(await screen.findByLabelText("Email"), "a@b.io");
    await user.click(screen.getByRole("button", { name: "Send reset link" }));

    expect(await screen.findByText(/reset link is on its way/)).toBeInTheDocument();
  });
});
