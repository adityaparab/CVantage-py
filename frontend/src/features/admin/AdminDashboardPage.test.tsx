import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { AdminDashboardPage } from "@/features/admin/AdminDashboardPage";
import { server } from "@/test/server";

describe("AdminDashboardPage", () => {
  it("renders the platform stat cards", async () => {
    server.use(
      http.get("*/api/v1/admin/stats", () =>
        HttpResponse.json({ registeredUsers: 42, totalResumes: 128, totalAnalyses: 256 }),
      ),
    );
    render(
      <QueryClientProvider client={createQueryClient()}>
        <AdminDashboardPage />
      </QueryClientProvider>,
    );
    expect(await screen.findByText("42")).toBeInTheDocument();
    expect(screen.getByText("128")).toBeInTheDocument();
    expect(screen.getByText("256")).toBeInTheDocument();
    expect(screen.getByText("Registered users")).toBeInTheDocument();
  });
});
