import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { MAX_UPLOAD_BYTES, validateUploadFile } from "@/api/upload";
import { UploadPage } from "@/features/upload/UploadPage";
import { server } from "@/test/server";

function pdf(name = "resume.pdf"): File {
  return new File(["%PDF-1.4 data"], name, { type: "application/pdf" });
}

describe("validateUploadFile", () => {
  it("rejects unsupported types", () => {
    const txt = new File(["x"], "notes.txt", { type: "text/plain" });
    expect(validateUploadFile(txt)).toMatch(/PDF, DOC, and DOCX/);
  });

  it("rejects oversized files", () => {
    const big = new File([new Uint8Array(MAX_UPLOAD_BYTES + 1)], "big.pdf", {
      type: "application/pdf",
    });
    expect(validateUploadFile(big)).toMatch(/10 MB/);
  });

  it("accepts a valid pdf", () => {
    expect(validateUploadFile(pdf())).toBeNull();
  });
});

function renderUpload() {
  const router = createMemoryRouter(
    [
      { path: "/upload", element: <UploadPage /> },
      { path: "/resumes/:id/review", element: <p>Review screen</p> },
    ],
    { initialEntries: ["/upload"] },
  );
  return render(<RouterProvider router={router} />);
}

describe("UploadPage", () => {
  it("rejects an invalid dropped file client-side", () => {
    renderUpload();
    const dropzone = screen.getByText(/Drag & drop a file/).closest("button")!;
    fireEvent.drop(dropzone, {
      dataTransfer: { files: [new File(["x"], "notes.txt", { type: "text/plain" })] },
    });
    expect(screen.getByRole("alert")).toHaveTextContent(/PDF, DOC, and DOCX/);
  });

  it("highlights the dropzone while dragging over it", () => {
    renderUpload();
    const dropzone = screen.getByText(/Drag & drop a file/).closest("button")!;
    fireEvent.dragOver(dropzone);
    expect(dropzone.className).toMatch(/border-accent\b/);
    fireEvent.dragLeave(dropzone);
    expect(dropzone.className).toMatch(/border-border\b/);
  });

  it("uploads a valid file and navigates to the review screen", async () => {
    server.use(
      http.post("*/api/v1/resumes/upload", () =>
        HttpResponse.json({ id: "r9", name: "resume.pdf" }),
      ),
    );
    const user = userEvent.setup();
    renderUpload();
    await user.upload(screen.getByLabelText("Choose a resume file"), pdf());
    expect(await screen.findByText("Review screen")).toBeInTheDocument();
  });
});
