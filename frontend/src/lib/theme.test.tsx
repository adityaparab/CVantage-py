import { act, render, renderHook, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";
import { ThemeToggle } from "@/components/ui";
import { ThemeProvider, useTheme } from "@/lib/theme";

afterEach(() => {
  document.documentElement.classList.remove("dark");
  localStorage.clear();
});

describe("useTheme", () => {
  it("toggles the dark class and persists the choice", () => {
    const { result } = renderHook(() => useTheme(), { wrapper: ThemeProvider });

    expect(result.current.theme).toBe("light");
    act(() => result.current.toggleTheme());

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("cvantage-theme")).toBe("dark");
  });

  it("throws when used outside a provider", () => {
    expect(() => renderHook(() => useTheme())).toThrow(/ThemeProvider/);
  });
});

describe("ThemeToggle", () => {
  it("flips the theme on click with an accessible label", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );
    const button = screen.getByRole("button", { name: /dark theme/i });
    await user.click(button);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByRole("button", { name: /light theme/i })).toBeInTheDocument();
  });
});
