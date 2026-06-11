import { renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { cn } from "@/lib/cn";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

describe("cn", () => {
  it("joins truthy classes and drops falsy ones", () => {
    expect(cn("a", false, "b", null, undefined, "c")).toBe("a b c");
  });
});

describe("useDocumentTitle", () => {
  it("sets a suffixed title and restores it on unmount", () => {
    const original = document.title;
    const { unmount } = renderHook(() => useDocumentTitle("Dashboard"));
    expect(document.title).toBe("Dashboard · CVantage");
    unmount();
    expect(document.title).toBe(original);
  });

  it("uses the bare brand for an empty title", () => {
    renderHook(() => useDocumentTitle(""));
    expect(document.title).toBe("CVantage");
  });
});
