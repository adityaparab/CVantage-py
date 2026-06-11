import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import { deleteResume, getDashboardStats, listResumes, type ResumeListItem } from "@/api/resumes";
import {
  Badge,
  Button,
  EmptyState,
  Modal,
  Skeleton,
  Table,
  useToast,
  type Column,
} from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

const STATUS_TONE = {
  unanalyzed: "neutral",
  in_progress: "warn",
  completed: "success",
  failed: "danger",
} as const;

const STATUS_LABEL = {
  unanalyzed: "Unanalyzed",
  in_progress: "In progress",
  completed: "Completed",
  failed: "Failed",
} as const;

function StatCard({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-card border border-border bg-card p-5">
      <p className="text-sm text-muted">{label}</p>
      {value === undefined ? (
        <Skeleton className="mt-2 h-8 w-12" />
      ) : (
        <p className="mt-1 text-3xl font-bold text-text">{value}</p>
      )}
    </div>
  );
}

export function DashboardPage() {
  useDocumentTitle("Dashboard");
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [pendingDelete, setPendingDelete] = useState<ResumeListItem | null>(null);

  const stats = useQuery({ queryKey: queryKeys.resumes.stats, queryFn: getDashboardStats });
  const resumes = useQuery({ queryKey: queryKeys.resumes.list(), queryFn: () => listResumes() });

  const deleteMutation = useMutation({
    mutationFn: deleteResume,
    onMutate: async (id: string) => {
      await queryClient.cancelQueries({ queryKey: queryKeys.resumes.list() });
      const previous = queryClient.getQueryData(queryKeys.resumes.list());
      queryClient.setQueryData(queryKeys.resumes.list(), (old: typeof resumes.data) =>
        old ? { ...old, items: old.items.filter((r) => r.id !== id), total: old.total - 1 } : old,
      );
      return { previous };
    },
    onError: (e, _id, context) => {
      if (context?.previous) queryClient.setQueryData(queryKeys.resumes.list(), context.previous);
      toast(toApiError(e).message, "danger");
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: queryKeys.resumes.all }),
  });

  const columns: Column<ResumeListItem>[] = [
    {
      key: "name",
      header: "Name",
      render: (r) => (
        <Link to={`/resumes/${r.id}`} className="font-medium text-accent-text hover:underline">
          {r.name}
        </Link>
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (r) => (
        <Badge tone={STATUS_TONE[r.analysis_status]}>{STATUS_LABEL[r.analysis_status]}</Badge>
      ),
    },
    {
      key: "created",
      header: "Created",
      render: (r) => new Date(r.created_at).toLocaleDateString(),
    },
    { key: "count", header: "Analyses", render: (r) => r.analysis_count },
    {
      key: "actions",
      header: "",
      render: (r) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="secondary" onClick={() => navigate(`/analyses/new/${r.id}`)}>
            Analyze
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setPendingDelete(r)}>
            Delete
          </Button>
        </div>
      ),
      className: "text-right",
    },
  ];

  const items = resumes.data?.items ?? [];

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-text">Dashboard</h1>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => navigate("/upload")}>
            Upload resume
          </Button>
          <Button onClick={() => navigate("/resumes/new")}>Create resume</Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <StatCard label="Resumes created" value={stats.data?.resumeCount} />
        <StatCard label="Analyses run" value={stats.data?.analysisCount} />
      </div>

      <section>
        <h2 className="mb-3 text-lg font-semibold text-text">Your resumes</h2>
        {resumes.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : items.length === 0 ? (
          <EmptyState
            title="No resumes yet"
            description="Create a resume or upload an existing file to get started."
            action={<Button onClick={() => navigate("/resumes/new")}>Create resume</Button>}
          />
        ) : (
          <Table<ResumeListItem> columns={columns} rows={items} rowKey={(r) => r.id} />
        )}
      </section>

      <Modal
        open={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete resume?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (pendingDelete) deleteMutation.mutate(pendingDelete.id);
                setPendingDelete(null);
              }}
            >
              Delete
            </Button>
          </>
        }
      >
        “{pendingDelete?.name}” and its analyses will be permanently removed.
      </Modal>
    </div>
  );
}
