import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { createQueryClient } from "@/api/queryClient";
import { ToastProvider } from "@/components/ui";
import { AdminSettingsPage } from "@/features/admin/AdminSettingsPage";
import { server } from "@/test/server";

function model(id: string, last4: string) {
  return {
    id,
    modelName: "gpt-4o",
    provider: "openai",
    apiKeyLast4: last4,
    usages: ["analysis"],
    status: "active",
  };
}

function renderSettings() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <ToastProvider>
        <AdminSettingsPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("AdminSettingsPage", () => {
  it("shows models with masked keys only", async () => {
    server.use(
      http.get("*/api/v1/admin/models", () => HttpResponse.json({ items: [model("m1", "3kF9")] })),
    );
    renderSettings();
    expect(await screen.findByText("••••3kF9")).toBeInTheDocument();
    expect(screen.getByText("openai/gpt-4o")).toBeInTheDocument();
  });

  it("surfaces an inline error when the API key fails validation", async () => {
    server.use(
      http.get("*/api/v1/admin/models", () => HttpResponse.json({ items: [] })),
      http.post("*/api/v1/admin/models", () =>
        HttpResponse.json(
          { detail: { message: "API key failed validation against the provider" } },
          { status: 422 },
        ),
      ),
    );
    const user = userEvent.setup();
    renderSettings();

    await user.type(await screen.findByLabelText("Model name"), "gpt-4o");
    await user.type(screen.getByLabelText("API key"), "sk-bad-key");
    await user.click(screen.getByRole("button", { name: "Add model" }));

    expect(await screen.findByText(/failed validation/)).toBeInTheDocument();
  });

  it("adds a model and shows it in the table", async () => {
    let created = false;
    server.use(
      http.get("*/api/v1/admin/models", () =>
        HttpResponse.json({ items: created ? [model("m9", "9999")] : [] }),
      ),
      http.post("*/api/v1/admin/models", () => {
        created = true;
        return HttpResponse.json(model("m9", "9999"), { status: 201 });
      }),
    );
    const user = userEvent.setup();
    renderSettings();

    await user.type(await screen.findByLabelText("Model name"), "gpt-4o");
    await user.type(screen.getByLabelText("API key"), "sk-good-key-9999");
    await user.click(screen.getByRole("button", { name: "Add model" }));

    await waitFor(() => expect(screen.getByText("••••9999")).toBeInTheDocument());
  });

  it("disables, rotates, and deletes a model", async () => {
    const calls: string[] = [];
    server.use(
      http.get("*/api/v1/admin/models", () => HttpResponse.json({ items: [model("m1", "3kF9")] })),
      http.patch("*/api/v1/admin/models/m1", () => {
        calls.push("disable");
        return HttpResponse.json({ ...model("m1", "3kF9"), status: "disabled" });
      }),
      http.post("*/api/v1/admin/models/m1/rotate-key", () => {
        calls.push("rotate");
        return HttpResponse.json({ ...model("m1", "8888") });
      }),
      http.delete("*/api/v1/admin/models/m1", () => {
        calls.push("delete");
        return new HttpResponse(null, { status: 200 });
      }),
    );
    const user = userEvent.setup();
    renderSettings();

    await screen.findByText("••••3kF9");
    await user.click(screen.getByRole("button", { name: "Disable" }));
    await waitFor(() => expect(calls).toContain("disable"));

    await user.click(screen.getByRole("button", { name: "Rotate key" }));
    await user.type(screen.getByLabelText("New API key"), "sk-rotated-8888");
    await user.click(screen.getByRole("button", { name: "Rotate" }));
    await waitFor(() => expect(calls).toContain("rotate"));

    await user.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(calls).toContain("delete"));
  });
});
