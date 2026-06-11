import { useState } from "react";
import { Button, Input, Textarea } from "@/components/ui";

/**
 * In-place editable text. Shows the value with a keyboard-accessible pencil
 * affordance (revealed on hover/focus); clicking it swaps to an input with
 * Save/Cancel. Save delegates to `onSave`, which performs the PATCH.
 */
export function EditableText({
  value,
  label,
  placeholder = "—",
  multiline = false,
  onSave,
}: {
  value: string;
  label: string;
  placeholder?: string;
  multiline?: boolean;
  onSave: (next: string) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [saving, setSaving] = useState(false);

  async function commit() {
    setSaving(true);
    try {
      await onSave(draft.trim());
      setEditing(false);
    } finally {
      setSaving(false);
    }
  }

  if (editing) {
    return (
      <div className="flex items-start gap-2">
        {multiline ? (
          <Textarea
            label={label}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={3}
          />
        ) : (
          <Input label={label} value={draft} onChange={(e) => setDraft(e.target.value)} />
        )}
        <div className="mt-7 flex gap-1">
          <Button size="sm" onClick={commit} loading={saving}>
            Save
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
            Cancel
          </Button>
        </div>
      </div>
    );
  }

  return (
    <span className="group inline-flex items-center gap-1.5">
      <span className={value ? "text-text" : "italic text-muted"}>{value || placeholder}</span>
      <button
        type="button"
        aria-label={`Edit ${label}`}
        onClick={() => {
          setDraft(value);
          setEditing(true);
        }}
        className="rounded p-0.5 text-muted opacity-0 transition-opacity hover:text-accent-text focus-visible:opacity-100 focus-visible:outline-2 focus-visible:outline-accent group-hover:opacity-100"
      >
        ✎
      </button>
    </span>
  );
}
