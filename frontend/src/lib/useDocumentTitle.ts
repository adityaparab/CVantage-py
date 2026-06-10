import { useEffect } from "react";

/** Sets the document title for the current route, restoring the base on unmount. */
export function useDocumentTitle(title: string): void {
  useEffect(() => {
    const previous = document.title;
    document.title = title ? `${title} · CVantage` : "CVantage";
    return () => {
      document.title = previous;
    };
  }, [title]);
}
