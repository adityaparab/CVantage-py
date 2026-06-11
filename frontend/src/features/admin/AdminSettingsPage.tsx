import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  createAdminModel,
  deleteAdminModel,
  listAdminModels,
  rotateAdminModelKey,
  updateAdminModel,
  type AdminModel,
} from "@/api/admin";
import { toApiError } from "@/api/errors";
import { queryKeys } from "@/api/queryKeys";
import {
  Badge,
  Button,
  Checkbox,
  Input,
  Modal,
  Skeleton,
  Table,
  useToast,
  type Column,
} from "@/components/ui";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

const USAGES = [
  { value: "resume_parsing", label: "Resume parsing" },
  { value: "analysis", label: "Analysis" },
  { value: "fallback", label: "Fallback" },
];

function AddModelForm({ onAdded }: { onAdded: () => void }) {
  const { toast } = useToast();
  const [modelName, setModelName] = useState("");
  const [provider, setProvider] = useState("openai");
  const [apiKey, setApiKey] = useState("");
  const [usages, setUsages] = useState<string[]>(["analysis"]);
  const [error, setError] = useState<string>();

  const create = useMutation({
    mutationFn: () => createAdminModel({ modelName, provider, apiKey, usages }),
    onSuccess: () => {
      toast("Model added.", "success");
      setModelName("");
      setApiKey("");
      setError(undefined);
      onAdded();
    },
    onError: (e) => setError(toApiError(e).message),
  });

  return (
    <form
      className="rounded-card border border-border bg-card p-6"
      onSubmit={(e) => {
        e.preventDefault();
        setError(undefined);
        if (modelName && provider && apiKey && usages.length) create.mutate();
      }}
    >
      <h2 className="mb-4 text-sm font-semibold uppercase text-muted">Add a model</h2>
      {error && (
        <p role="alert" className="mb-3 rounded-md bg-danger-bg px-3 py-2 text-sm text-danger">
          {error}
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-2">
        <Input label="Provider" value={provider} onChange={(e) => setProvider(e.target.value)} />
        <Input
          label="Model name"
          value={modelName}
          onChange={(e) => setModelName(e.target.value)}
        />
      </div>
      <div className="mt-4">
        <Input
          label="API key"
          type="password"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          description="Validated with a live provider ping before it is stored encrypted."
        />
      </div>
      <fieldset className="mt-4">
        <legend className="mb-2 text-sm font-medium text-text">Usages</legend>
        <div className="flex flex-wrap gap-4">
          {USAGES.map((u) => (
            <Checkbox
              key={u.value}
              label={u.label}
              checked={usages.includes(u.value)}
              onChange={(e) =>
                setUsages((prev) =>
                  e.target.checked ? [...prev, u.value] : prev.filter((v) => v !== u.value),
                )
              }
            />
          ))}
        </div>
      </fieldset>
      <Button
        className="mt-4"
        type="submit"
        loading={create.isPending}
        disabled={!modelName || !apiKey || usages.length === 0}
      >
        Add model
      </Button>
    </form>
  );
}

export function AdminSettingsPage() {
  useDocumentTitle("Settings");
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [rotating, setRotating] = useState<AdminModel | null>(null);
  const [newKey, setNewKey] = useState("");

  const models = useQuery({ queryKey: queryKeys.admin.models, queryFn: listAdminModels });

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: queryKeys.admin.models });
  }

  const toggle = useMutation({
    mutationFn: (m: AdminModel) =>
      updateAdminModel(m.id, { status: m.status === "active" ? "disabled" : "active" }),
    onSuccess: refresh,
    onError: (e) => toast(toApiError(e).message, "danger"),
  });
  const rotate = useMutation({
    mutationFn: () => rotateAdminModelKey(rotating!.id, newKey),
    onSuccess: () => {
      toast("Key rotated.", "success");
      setRotating(null);
      setNewKey("");
      refresh();
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });
  const remove = useMutation({
    mutationFn: deleteAdminModel,
    onSuccess: () => {
      toast("Model deleted.", "success");
      refresh();
    },
    onError: (e) => toast(toApiError(e).message, "danger"),
  });

  const columns: Column<AdminModel>[] = [
    { key: "model", header: "Model", render: (m) => `${m.provider}/${m.modelName}` },
    {
      key: "key",
      header: "API key",
      render: (m) => <span className="font-mono">••••{m.apiKeyLast4}</span>,
    },
    { key: "usages", header: "Usages", render: (m) => m.usages.join(", ") },
    {
      key: "status",
      header: "Status",
      render: (m) => <Badge tone={m.status === "active" ? "success" : "neutral"}>{m.status}</Badge>,
    },
    {
      key: "actions",
      header: "",
      className: "text-right",
      render: (m) => (
        <div className="flex justify-end gap-2">
          <Button size="sm" variant="ghost" onClick={() => toggle.mutate(m)}>
            {m.status === "active" ? "Disable" : "Enable"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setRotating(m)}>
            Rotate key
          </Button>
          <Button size="sm" variant="ghost" onClick={() => remove.mutate(m.id)}>
            Delete
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-bold text-text">AI model settings</h1>

      {models.isLoading ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <Table<AdminModel>
          columns={columns}
          rows={models.data?.items ?? []}
          rowKey={(m) => m.id}
          emptyMessage="No models configured — add one below."
        />
      )}

      <AddModelForm onAdded={refresh} />

      <Modal
        open={rotating !== null}
        onClose={() => setRotating(null)}
        title="Rotate API key"
        footer={
          <>
            <Button variant="ghost" onClick={() => setRotating(null)}>
              Cancel
            </Button>
            <Button loading={rotate.isPending} disabled={!newKey} onClick={() => rotate.mutate()}>
              Rotate
            </Button>
          </>
        }
      >
        <Input
          label="New API key"
          type="password"
          value={newKey}
          onChange={(e) => setNewKey(e.target.value)}
        />
      </Modal>
    </div>
  );
}
