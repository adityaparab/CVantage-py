import { QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createQueryClient } from "@/api/queryClient";
import { RootErrorBoundary } from "@/app/RootErrorBoundary";
import { AppRouter } from "@/app/router";
import { ToastProvider } from "@/components/ui";
import { AuthProvider } from "@/lib/auth";
import { initSentry } from "@/lib/sentry";
import { ThemeProvider } from "@/lib/theme";
import "@/styles/index.css";

void initSentry();

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Root element #root was not found");
}

const queryClient = createQueryClient();

createRoot(rootElement).render(
  <StrictMode>
    <RootErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <ThemeProvider>
          <ToastProvider>
            <AuthProvider>
              <AppRouter />
            </AuthProvider>
          </ToastProvider>
        </ThemeProvider>
      </QueryClientProvider>
    </RootErrorBoundary>
  </StrictMode>,
);
