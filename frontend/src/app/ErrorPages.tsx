import { Link } from "react-router-dom";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

function ErrorScreen({ code, title, message }: { code: string; title: string; message: string }) {
  useDocumentTitle(title);
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="bg-gradient-brand bg-clip-text text-5xl font-bold text-transparent">{code}</p>
      <h1 className="text-2xl font-bold text-text">{title}</h1>
      <p className="max-w-md text-muted">{message}</p>
      <Link
        to="/"
        className="mt-2 rounded-[10px] bg-accent px-5 py-2.5 text-sm font-medium text-white hover:opacity-90"
      >
        Back to home
      </Link>
    </div>
  );
}

export function NotFoundPage() {
  return (
    <ErrorScreen
      code="404"
      title="Page not found"
      message="The page you’re looking for doesn’t exist."
    />
  );
}

export function ForbiddenPage() {
  return (
    <ErrorScreen
      code="403"
      title="Access denied"
      message="You don’t have permission to view this page."
    />
  );
}
