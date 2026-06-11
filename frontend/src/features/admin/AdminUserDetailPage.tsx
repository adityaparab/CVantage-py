import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import {
  deactivateAdminUser,
  deleteAdminResume,
  getAdminUser,
  listAdminUserResumes,
  reactivateAdminUser,
  resetAdminUserPassword,
  updateAdminUser,
  type AdminUserResume,
} from "@/api/admin";
import { toApiError } from "@/api/errors";
import { Badge, Button, Input, Modal, Skeleton, useToast } from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function AdminUserDetailPage() {
  const { id = "" } = useParams();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [pendingDeleteResume, setPendingDeleteResume] = useState<AdminUserResume | null>(null);

  const user = useQuery({
    queryKey: ["admin", "user", id],
    queryFn: () => getAdminUser(id),
  });
  const resumes = useQuery({
    queryKey: ["admin", "user", id, "resumes"],
    queryFn: () => listAdminUserResumes(id),
  });
  useDocumentTitle(user.data?.fullName ?? "User");

  useEffect(() => {
    if (user.data) {
      setFullName(user.data.fullName);
      setEmail(user.data.email);
    }
  }, [user.data]);

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "user", id] });
  }

  const save = useMutation({
    mutationFn: () => updateAdminUser(id, { fullName, email }),
    onSuccess: () => {
      toast("User updated.", "success");
      refresh();
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });
  const resetPw = useMutation({
    mutationFn: () => resetAdminUserPassword(id),
    onSuccess: (r) => toast(`Password reset (${r.method.replace("_", " ")}).`, "success"),
    onError: (e) => toast(toApiError(e).message, "danger"),
  });
  const setActive = useMutation({
    mutationFn: (active: boolean) => (active ? reactivateAdminUser(id) : deactivateAdminUser(id)),
    onSuccess: () => {
      toast("Status updated.", "success");
      refresh();
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });
  const deleteResume = useMutation({
    mutationFn: deleteAdminResume,
    onSuccess: () => {
      toast("Resume deleted.", "success");
      void queryClient.invalidateQueries({ queryKey: ["admin", "user", id, "resumes"] });
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  if (user.isLoading) return <Skeleton className="h-64 w-full" />;
  if (user.isError || !user.data) return <p className="text-danger">Could not load this user.</p>;
  const u = user.data;
  const active = u.status === "active";

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-text">{u.fullName}</h1>
          <Badge tone={active ? "success" : "neutral"}>{u.status}</Badge>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" loading={resetPw.isPending} onClick={() => resetPw.mutate()}>
            Reset password
          </Button>
          <Button
            variant={active ? "danger" : "primary"}
            loading={setActive.isPending}
            onClick={() => setActive.mutate(!active)}
          >
            {active ? "Deactivate" : "Reactivate"}
          </Button>
        </div>
      </div>

      <section className="rounded-card border border-border bg-card p-6">
        <h2 className="mb-4 text-sm font-semibold uppercase text-muted">Profile</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Input label="Full name" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          <Input label="Email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <Button className="mt-4" loading={save.isPending} onClick={() => save.mutate()}>
          Save changes
        </Button>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase text-muted">Resumes (metadata only)</h2>
        {resumes.data?.items.length === 0 ? (
          <p className="text-sm text-muted">This user has no resumes.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {(resumes.data?.items ?? []).map((r) => (
              <li
                key={r.id}
                className="flex items-center justify-between rounded-card border border-border p-3"
              >
                <div>
                  <p className="font-medium text-text">{r.name}</p>
                  <p className="text-xs text-muted">
                    {r.analysisCount} analyses · {r.analysisStatus}
                  </p>
                </div>
                <Button size="sm" variant="ghost" onClick={() => setPendingDeleteResume(r)}>
                  Delete
                </Button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <Modal
        open={pendingDeleteResume !== null}
        onClose={() => setPendingDeleteResume(null)}
        title="Delete resume?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setPendingDeleteResume(null)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              onClick={() => {
                if (pendingDeleteResume) deleteResume.mutate(pendingDeleteResume.id);
                setPendingDeleteResume(null);
              }}
            >
              Delete
            </Button>
          </>
        }
      >
        Deleting “{pendingDeleteResume?.name}” cascades to its analyses and clears their
        notifications. This cannot be undone.
      </Modal>
    </div>
  );
}
