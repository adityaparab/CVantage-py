import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "@/App";
import { ToastProvider } from "@/components/ui";
import { ThemeProvider } from "@/lib/theme";
import "@/styles/index.css";

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root was not found");
}

createRoot(rootElement).render(
  <StrictMode>
    <ThemeProvider>
      <ToastProvider>
        <App />
      </ToastProvider>
    </ThemeProvider>
  </StrictMode>,
);
