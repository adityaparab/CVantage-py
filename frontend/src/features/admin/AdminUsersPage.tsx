import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { deactivateAdminUser, listAdminUsers, type AdminUser } from "@/api/admin";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import {
  Badge,
  Button,
  Input,
  Modal,
  Skeleton,
  Table,
  useToast,
  type Column,
} from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useDebounce } from "@/lib/useDebounce";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function AdminUsersPage() {
  useDocumentTitle("Users");
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const [pendingDeactivate, setPendingDeactivate] = useState<AdminUser | null>(null);
  const debouncedSearch = useDebounce(search);

  const users = useQuery({
    queryKey: queryKeys.admin.users({ search: debouncedSearch }),
    queryFn: () => listAdminUsers({ search: debouncedSearch || undefined, limit: 50 }),
  });

  const deactivate = useMutation({
    mutationFn: deactivateAdminUser,
    onSuccess: () => {
      toast("User deactivated.", "success");
      void queryClient.invalidateQueries({ queryKey: queryKeys.admin.users() });
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  const columns: Column<AdminUser>[] = [
    {
      key: "name",
      header: "Name",
      render: (u) => (
        <Link to={`/admin/users/${u.id}`} className="font-medium text-accent-text hover:underline">
          {u.fullName}
        </Link>
      ),
    },
    { key: "email", header: "Email", render: (u) => u.email },
    {
      key: "status",
      header: "Status",
      render: (u) => <Badge tone={u.status === "active" ? "success" : "neutral"}>{u.status}</Badge>,
    },
    { key: "resumes", header: "Resumes", render: (u) => u.resumeCount },
    { key: "analyses", header: "Analyses", render: (u) => u.analysisCount },
    {
      key: "actions",
      header: "",
      className: "text-right",
      render: (u) =>
        u.id === user?.id || u.status !== "active" ? null : (
          <Button size="sm" variant="ghost" onClick={() => setPendingDeactivate(u)}>
            Deactivate
          </Button>
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold text-text">Users</h1>
      <Input
        label="Search"
        placeholder="Search by name, email, or id"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />
      {users.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <Table<AdminUser>
          columns={columns}
          rows={users.data?.items ?? []}
          rowKey={(u) => u.id}
          emptyMessage="No users found"
        />
      )}

      <Modal
        open={pendingDeactivate !== null}
        onClose={() => setPendingDeactivate(null)}
        title="Deactivate user?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDeactivate(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (pendingDeactivate) deactivate.mutate(pendingDeactivate.id);
                setPendingDeactivate(null);
              }}
            >
              Deactivate
            </Button>
          </>
        }
      >
        {pendingDeactivate?.fullName} will lose access and all their sessions will be revoked.
      </Modal>
    </div>
  );
}
