import { clsx, type ClassValue } from "clsx";

/** Conditional Tailwind class composition. */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs);
}
