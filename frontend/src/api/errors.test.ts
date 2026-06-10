import { AxiosError, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";
import { ApiError, toApiError } from "@/api/errors";

function axiosErrorWith(status: number, data: unknown): AxiosError {
  const err = new AxiosError("Request failed");
  err.response = { status, data } as AxiosResponse;
  return err;
}

describe("toApiError", () => {
  it("extracts a string HTTPException detail", () => {
    const err = toApiError(axiosErrorWith(404, { detail: "Resume not found" }));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.statusCode).toBe(404);
    expect(err.message).toBe("Resume not found");
  });

  it("extracts a structured detail.message", () => {
    const err = toApiError(axiosErrorWith(422, { detail: { message: "Validation failed" } }));
    expect(err.message).toBe("Validation failed");
  });

  it("surfaces the problem-details envelope message", () => {
    const err = toApiError(
      axiosErrorWith(409, { statusCode: 409, error: "Conflict", message: "Email already in use" }),
    );
    expect(err.message).toBe("Email already in use");
    expect(err.envelope?.error).toBe("Conflict");
  });

  it("falls back for non-axios errors", () => {
    const err = toApiError(new Error("boom"));
    expect(err.statusCode).toBe(0);
    expect(err.message).toBe("boom");
  });
});
