import { describe, expect, it } from "vitest";
import { emptyResumeForm, pruneEmpty, toJsonResume } from "@/features/resume/jsonResume";

describe("pruneEmpty", () => {
  it("drops empty strings, arrays, and objects but keeps real values", () => {
    expect(
      pruneEmpty({ a: "  ", b: "x", c: [], d: ["", "y"], e: { f: "" }, g: { h: "z" } }),
    ).toEqual({ b: "x", d: ["y"], g: { h: "z" } });
  });

  it("returns undefined for an entirely empty structure", () => {
    expect(pruneEmpty({ a: "", b: [], c: { d: "" } })).toBeUndefined();
  });
});

describe("toJsonResume", () => {
  it("prunes placeholders and unwraps highlight/keyword values", () => {
    const form = emptyResumeForm("Backend Engineer");
    form.basics.name = "Ada Lovelace";
    form.basics.email = "";
    form.work = [
      {
        name: "Acme",
        position: "Engineer",
        location: "",
        url: "",
        startDate: "2022",
        endDate: "",
        summary: "",
        highlights: [{ value: "Shipped X" }, { value: "" }],
      },
    ];
    form.skills = [{ name: "python", level: "", keywords: [{ value: "fastapi" }] }];

    const payload = toJsonResume(form) as Record<string, unknown>;
    expect(payload).toEqual({
      basics: { name: "Ada Lovelace" },
      work: [{ name: "Acme", position: "Engineer", startDate: "2022", highlights: ["Shipped X"] }],
      skills: [{ name: "python", keywords: ["fastapi"] }],
    });
  });

  it("produces an empty object for a blank resume", () => {
    expect(toJsonResume(emptyResumeForm())).toEqual({});
  });
});
