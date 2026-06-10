import { useFieldArray, useFormContext, type FieldValues, type ArrayPath } from "react-hook-form";
import { Button } from "@/components/ui";

/**
 * Array-field helper for repeatable json-resume sections (work, education, …).
 * Renders each item via the `children` render-prop and provides add / remove /
 * reorder (move up/down) controls.
 */
export function ArrayField<T extends FieldValues>({
  name,
  newItem,
  addLabel = "Add item",
  children,
}: {
  name: ArrayPath<T>;
  newItem: () => unknown;
  addLabel?: string;
  children: (index: number) => React.ReactNode;
}) {
  const { control } = useFormContext<T>();
  const { fields, append, remove, move } = useFieldArray<T>({ control, name });

  return (
    <div className="flex flex-col gap-4">
      {fields.map((field, index) => (
        <div key={field.id} className="rounded-card border border-border p-4">
          {children(index)}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label="Move up"
              disabled={index === 0}
              onClick={() => move(index, index - 1)}
            >
              ↑
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              aria-label="Move down"
              disabled={index === fields.length - 1}
              onClick={() => move(index, index + 1)}
            >
              ↓
            </Button>
            <Button type="button" size="sm" variant="danger" onClick={() => remove(index)}>
              Remove
            </Button>
          </div>
        </div>
      ))}
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <Button type="button" variant="secondary" onClick={() => append(newItem() as any)}>
        {addLabel}
      </Button>
    </div>
  );
}
