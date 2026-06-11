import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { OAuthButtons } from "@/features/auth/OAuthButtons";
import { ResetPasswordPage } from "@/features/auth/ResetPasswordPage";
import { server } from "@/test/server";

function withQuery(node: React.ReactNode) {
  return <QueryClientProvider client={createQueryClient()}>{node}</QueryClientProvider>;
}

describe("OAuthButtons", () => {
  it("renders only enabled providers", async () => {
    server.use(
      http.get("*/api/v1/auth/providers", () =>
        HttpResponse.json({ google: true, linkedin: false }),
      ),
    );
    render(withQuery(<OAuthButtons />));
    expect(await screen.findByRole("button", { name: /Continue with Google/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /LinkedIn/ })).not.toBeInTheDocument();
  });

  it("renders nothing when all providers are disabled", async () => {
    server.use(
      http.get("*/api/v1/auth/providers", () =>
        HttpResponse.json({ google: false, linkedin: false }),
      ),
    );
    const { container } = render(withQuery(<OAuthButtons />));
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});

function renderReset(path: string) {
  const router = createMemoryRouter(
    [
      { path: "/reset-password", element: <ResetPasswordPage /> },
      { path: "/login", element: <p>Login</p> },
    ],
    { initialEntries: [path] },
  );
  return render(<RouterProvider router={router} />);
}

describe("ResetPasswordPage", () => {
  it("shows the form when a token is present", () => {
    renderReset("/reset-password?token=abc123token");
    expect(screen.getByLabelText("New password")).toBeInTheDocument();
  });

  it("warns when the token is missing", () => {
    renderReset("/reset-password");
    expect(screen.getByRole("alert")).toHaveTextContent(/missing its token/);
  });
});
