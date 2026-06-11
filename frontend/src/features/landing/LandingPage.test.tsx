import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { LandingPage } from "@/features/landing/LandingPage";

describe("LandingPage", () => {
  it("renders the hero, features, and CTAs", () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("heading", { name: /Tailor your resume to every job/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("How it works")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /get started/i }).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /^Log in$/i })).toHaveAttribute("href", "/login");
  });
});
