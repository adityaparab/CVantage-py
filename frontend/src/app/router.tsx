import { lazy, Suspense, type ComponentType } from "react";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { AdminLayout, CandidateLayout, PublicLayout } from "@/components/layout/AppLayouts";
import { Spinner } from "@/components/ui";
import { RedirectIfAuthed, RequireAuth, RequireRole } from "@/app/guards";
import { ForbiddenPage, NotFoundPage } from "@/app/ErrorPages";

// Lazy-load each route so the build emits per-route chunks (code splitting).
function lazyNamed<T extends Record<string, ComponentType<unknown>>>(
  loader: () => Promise<T>,
  name: keyof T,
) {
  return lazy(() => loader().then((mod) => ({ default: mod[name] })));
}

const LandingPage = lazyNamed(() => import("@/features/landing/LandingPage"), "LandingPage");
const LoginPage = lazyNamed(() => import("@/features/auth/LoginPage"), "LoginPage");
const RegisterPage = lazyNamed(() => import("@/features/auth/RegisterPage"), "RegisterPage");
const ForgotPasswordPage = lazyNamed(
  () => import("@/features/auth/ForgotPasswordPage"),
  "ForgotPasswordPage",
);
const ResetPasswordPage = lazyNamed(
  () => import("@/features/auth/ResetPasswordPage"),
  "ResetPasswordPage",
);
const DashboardPage = lazyNamed(
  () => import("@/features/dashboard/DashboardPage"),
  "DashboardPage",
);
const UploadPage = lazyNamed(() => import("@/features/upload/UploadPage"), "UploadPage");
const ResumeEditorPage = lazyNamed(
  () => import("@/features/resume/ResumeEditorPage"),
  "ResumeEditorPage",
);
const ResumeViewPage = lazyNamed(
  () => import("@/features/resume/ResumeViewPage"),
  "ResumeViewPage",
);
const AnalysisStartPage = lazyNamed(
  () => import("@/features/analysis/AnalysisStartPage"),
  "AnalysisStartPage",
);
const AnalysisDetailPage = lazyNamed(
  () => import("@/features/analysis/AnalysisDetailPage"),
  "AnalysisDetailPage",
);
const ApplySuggestionsPage = lazyNamed(
  () => import("@/features/analysis/ApplySuggestionsPage"),
  "ApplySuggestionsPage",
);
const AdminDashboardPage = lazyNamed(
  () => import("@/features/admin/AdminDashboardPage"),
  "AdminDashboardPage",
);
const AdminUsersPage = lazyNamed(() => import("@/features/admin/AdminUsersPage"), "AdminUsersPage");
const AdminUserDetailPage = lazyNamed(
  () => import("@/features/admin/AdminUserDetailPage"),
  "AdminUserDetailPage",
);
const AdminSettingsPage = lazyNamed(
  () => import("@/features/admin/AdminSettingsPage"),
  "AdminSettingsPage",
);
const ShowcasePage = lazyNamed(() => import("@/components/ui/Showcase"), "Showcase");

function Lazy({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner size="lg" />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

const router = createBrowserRouter([
  {
    element: <PublicLayout />,
    children: [
      {
        index: true,
        element: (
          <Lazy>
            <LandingPage />
          </Lazy>
        ),
      },
      {
        path: "login",
        element: (
          <RedirectIfAuthed>
            <Lazy>
              <LoginPage />
            </Lazy>
          </RedirectIfAuthed>
        ),
      },
      {
        path: "register",
        element: (
          <RedirectIfAuthed>
            <Lazy>
              <RegisterPage />
            </Lazy>
          </RedirectIfAuthed>
        ),
      },
      {
        path: "forgot-password",
        element: (
          <Lazy>
            <ForgotPasswordPage />
          </Lazy>
        ),
      },
      {
        path: "reset-password",
        element: (
          <Lazy>
            <ResetPasswordPage />
          </Lazy>
        ),
      },
    ],
  },
  {
    element: (
      <RequireAuth>
        <CandidateLayout />
      </RequireAuth>
    ),
    children: [
      {
        path: "dashboard",
        element: (
          <Lazy>
            <DashboardPage />
          </Lazy>
        ),
      },
      {
        path: "upload",
        element: (
          <Lazy>
            <UploadPage />
          </Lazy>
        ),
      },
      {
        path: "resumes/new",
        element: (
          <Lazy>
            <ResumeEditorPage />
          </Lazy>
        ),
      },
      {
        path: "resumes/:id",
        element: (
          <Lazy>
            <ResumeViewPage />
          </Lazy>
        ),
      },
      {
        path: "analyses/new/:resumeId",
        element: (
          <Lazy>
            <AnalysisStartPage />
          </Lazy>
        ),
      },
      {
        path: "analyses/:id",
        element: (
          <Lazy>
            <AnalysisDetailPage />
          </Lazy>
        ),
      },
      {
        path: "analyses/:id/apply",
        element: (
          <Lazy>
            <ApplySuggestionsPage />
          </Lazy>
        ),
      },
    ],
  },
  {
    element: (
      <RequireRole role="admin">
        <AdminLayout />
      </RequireRole>
    ),
    children: [
      {
        path: "admin",
        element: (
          <Lazy>
            <AdminDashboardPage />
          </Lazy>
        ),
      },
      {
        path: "admin/users",
        element: (
          <Lazy>
            <AdminUsersPage />
          </Lazy>
        ),
      },
      {
        path: "admin/users/:id",
        element: (
          <Lazy>
            <AdminUserDetailPage />
          </Lazy>
        ),
      },
      {
        path: "admin/settings",
        element: (
          <Lazy>
            <AdminSettingsPage />
          </Lazy>
        ),
      },
    ],
  },
  { path: "403", element: <ForbiddenPage /> },
  // Dev-only UI-kit showcase (issue #65).
  ...(import.meta.env.DEV
    ? [
        {
          path: "showcase",
          element: (
            <Lazy>
              <ShowcasePage />
            </Lazy>
          ),
        },
      ]
    : []),
  { path: "*", element: <NotFoundPage /> },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
