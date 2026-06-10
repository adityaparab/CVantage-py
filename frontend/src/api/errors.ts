import { AxiosError } from "axios";

/** Server problem-details envelope (mirrors the FastAPI error contract). */
export interface ErrorEnvelope {
  statusCode: number;
  error: string;
  message: string;
  details?: unknown;
  requestId?: string;
  path?: string;
}

export class ApiError extends Error {
  readonly statusCode: number;
  readonly envelope: ErrorEnvelope | null;

  constructor(message: string, statusCode: number, envelope: ErrorEnvelope | null) {
    super(message);
    this.name = "ApiError";
    this.statusCode = statusCode;
    this.envelope = envelope;
  }
}

function extractMessage(data: unknown): { message: string; envelope: ErrorEnvelope | null } {
  if (data && typeof data === "object") {
    const obj = data as Record<string, unknown>;
    // FastAPI HTTPException detail may be a string or an object with `message`.
    const detail = obj.detail;
    if (typeof detail === "string") {
      return { message: detail, envelope: null };
    }
    if (detail && typeof detail === "object" && "message" in detail) {
      return { message: String((detail as Record<string, unknown>).message), envelope: null };
    }
    if (typeof obj.message === "string") {
      return { message: obj.message, envelope: obj as unknown as ErrorEnvelope };
    }
  }
  return { message: "Something went wrong", envelope: null };
}

/** Normalize any axios/unknown error into an {@link ApiError}. */
export function toApiError(error: unknown): ApiError {
  if (error instanceof AxiosError) {
    const status = error.response?.status ?? 0;
    const { message, envelope } = extractMessage(error.response?.data);
    return new ApiError(message, status, envelope);
  }
  if (error instanceof Error) {
    return new ApiError(error.message, 0, null);
  }
  return new ApiError("Unknown error", 0, null);
}
