import { z } from "zod";

/** Mirrors the server password policy (≥8 chars, upper, lower, digit). */
const passwordSchema = z
  .string()
  .min(8, "At least 8 characters")
  .regex(/[A-Z]/, "Needs an uppercase letter")
  .regex(/[a-z]/, "Needs a lowercase letter")
  .regex(/[0-9]/, "Needs a number");

export const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});

export const registerSchema = z.object({
  fullName: z.string().min(1, "Your name is required").max(200),
  email: z.string().email("Enter a valid email"),
  password: passwordSchema,
});

export type LoginValues = z.infer<typeof loginSchema>;
export type RegisterValues = z.infer<typeof registerSchema>;

/** Password-strength score (0–4) for the register meter. */
export function passwordStrength(password: string): number {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[0-9]/.test(password)) score += 1;
  return score;
}
