import { describe, expect, it } from "vitest";
import { loginSchema, passwordStrength, registerSchema } from "@/features/auth/schemas";

describe("auth schemas", () => {
  it("rejects an invalid login email", () => {
    expect(loginSchema.safeParse({ email: "nope", password: "x" }).success).toBe(false);
  });

  it("accepts a valid login", () => {
    expect(loginSchema.safeParse({ email: "a@b.io", password: "x" }).success).toBe(true);
  });

  it("enforces the register password policy", () => {
    const weak = registerSchema.safeParse({
      fullName: "Ada",
      email: "a@b.io",
      password: "alllowercase",
    });
    expect(weak.success).toBe(false);

    const strong = registerSchema.safeParse({
      fullName: "Ada",
      email: "a@b.io",
      password: "StrongPass1",
    });
    expect(strong.success).toBe(true);
  });

  it("scores password strength 0–4", () => {
    expect(passwordStrength("")).toBe(0);
    expect(passwordStrength("abcdefgh")).toBe(2); // length + lowercase
    expect(passwordStrength("StrongPass1")).toBe(4);
  });
});
