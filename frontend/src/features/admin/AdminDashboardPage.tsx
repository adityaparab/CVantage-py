import { useQuery } from "@tanstack/react-query";
import { getAdminStats } from "@/api/admin";
import { queryKeys } from "@/api/queryKeys";
import { Skeleton } from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

function StatCard({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-card border border-border bg-card p-6">
      <p className="text-sm text-muted">{label}</p>
      {value === undefined ? (
        <Skeleton className="mt-2 h-9 w-16" />
      ) : (
        <p className="mt-1 text-3xl font-bold text-text">{value.toLocaleString()}</p>
      )}
    </div>
  );
}

export function AdminDashboardPage() {
  useDocumentTitle("Admin");
  const stats = useQuery({ queryKey: queryKeys.admin.stats, queryFn: getAdminStats });

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-text">Platform overview</h1>
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard label="Registered users" value={stats.data?.registeredUsers} />
        <StatCard label="Total resumes" value={stats.data?.totalResumes} />
        <StatCard label="Analyses run" value={stats.data?.totalAnalyses} />
      </div>
      {stats.isError && <p className="text-sm text-danger">Could not load platform statistics.</p>}
    </div>
  );
}
