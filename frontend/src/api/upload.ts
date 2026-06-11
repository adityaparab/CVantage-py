import { apiClient } from "@/api/client";

export const ACCEPTED_UPLOAD_TYPES: Record<string, string> = {
  "application/pdf": ".pdf",
  "application/msword": ".doc",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
};

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB

/** Client-side pre-check mirroring the server's size/type limits. */
export function validateUploadFile(file: File): string | null {
  const byExt = /\.(pdf|docx?|)$/i.test(file.name);
  if (!ACCEPTED_UPLOAD_TYPES[file.type] && !byExt) {
    return "Only PDF, DOC, and DOCX files are supported.";
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return "File is larger than the 10 MB limit.";
  }
  if (file.size === 0) {
    return "That file appears to be empty.";
  }
  return null;
}

export interface UploadedResume {
  id: string;
  name: string;
}

export async function uploadResume(
  file: File,
  onProgress?: (percent: number) => void,
): Promise<UploadedResume> {
  const form = new FormData();
  form.append("upload", file);
  const res = await apiClient.post<UploadedResume>("/resumes/upload", form, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (event) => {
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100));
      }
    },
  });
  return res.data;
}
