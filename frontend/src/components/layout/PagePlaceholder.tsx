import type { ReactNode } from "react";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

/** Shared shell for routes whose full UI lands in a later phase. */
export function PagePlaceholder({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: ReactNode;
}) {
  useDocumentTitle(title);
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-bold text-text">{title}</h1>
      {description && <p className="text-muted">{description}</p>}
      {children}
    </section>
  );
}
