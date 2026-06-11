import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { setAccessToken } from "@/api/token";
import { AuthProvider, useAuth } from "@/lib/auth";
import { authedHandlers } from "@/test/handlers";
import { server } from "@/test/server";

afterEach(() => setAccessToken(null));

function wrap(children: ReactNode) {
  return (
    <QueryClientProvider client={createQueryClient()}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}

function Probe() {
  const { user, isLoading, logout } = useAuth();
  if (isLoading) return <p>loading</p>;
  return (
    <div>
      <p>{user ? user.email : "anon"}</p>
      <button onClick={() => logout()}>Logout</button>
    </div>
  );
}

describe("AuthProvider", () => {
  it("exposes the authenticated user from the me query", async () => {
    server.use(...authedHandlers);
    render(wrap(<Probe />));
    expect(await screen.findByText("candidate@example.com")).toBeInTheDocument();
  });

  it("clears the user on logout", async () => {
    server.use(
      ...authedHandlers,
      http.post("*/api/v1/auth/logout", () => new HttpResponse(null, { status: 200 })),
    );
    const user = userEvent.setup();
    render(wrap(<Probe />));
    await screen.findByText("candidate@example.com");

    await user.click(screen.getByRole("button", { name: "Logout" }));
    await waitFor(() => expect(screen.getByText("anon")).toBeInTheDocument());
  });

  it("reports anon when the me query is unauthorized", async () => {
    server.use(
      http.get("*/api/v1/users/me", () => new HttpResponse(null, { status: 401 })),
      http.post("*/api/v1/auth/refresh", () => new HttpResponse(null, { status: 401 })),
    );
    render(wrap(<Probe />));
    expect(await screen.findByText("anon")).toBeInTheDocument();
  });
});
