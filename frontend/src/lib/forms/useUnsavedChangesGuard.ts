import { useEffect } from "react";
import { useBlocker } from "react-router-dom";

/**
 * Warns before leaving a dirty form — both for in-app navigation (via the
 * router blocker + a confirm) and for tab close / reload (beforeunload).
 */
export function useUnsavedChangesGuard(when: boolean): void {
  const blocker = useBlocker(when);

  useEffect(() => {
    if (blocker.state === "blocked") {
      const leave = window.confirm("You have unsaved changes. Leave without saving?");
      if (leave) {
        blocker.proceed();
      } else {
        blocker.reset();
      }
    }
  }, [blocker]);

  useEffect(() => {
    if (!when) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [when]);
}
