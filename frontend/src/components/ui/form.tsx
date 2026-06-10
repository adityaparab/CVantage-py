import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { cn } from "@/lib/cn";

const CONTROL_BASE =
  "w-full rounded-[10px] border border-border bg-card px-3 py-2 text-sm text-text " +
  "placeholder:text-muted focus-visible:outline-2 focus-visible:outline-accent " +
  "disabled:cursor-not-allowed disabled:opacity-60 aria-[invalid=true]:border-danger";

function FieldShell({
  id,
  label,
  description,
  error,
  children,
}: {
  id: string;
  label?: string;
  description?: string;
  error?: string;
  children: ReactNode;
}) {
  const descId = description ? `${id}-desc` : undefined;
  const errId = error ? `${id}-err` : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className="text-sm font-medium text-text">
          {label}
        </label>
      )}
      {description && (
        <p id={descId} className="text-xs text-muted">
          {description}
        </p>
      )}
      {children}
      {error && (
        <p id={errId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  description?: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  { label, description, error, id, className, ...props },
  ref,
) {
  const reactId = useId();
  const fieldId = id ?? reactId;
  return (
    <FieldShell id={fieldId} label={label} description={description} error={error}>
      <input
        ref={ref}
        id={fieldId}
        aria-invalid={error ? true : undefined}
        aria-describedby={
          [description ? `${fieldId}-desc` : "", error ? `${fieldId}-err` : ""]
            .filter(Boolean)
            .join(" ") || undefined
        }
        className={cn(CONTROL_BASE, className)}
        {...props}
      />
    </FieldShell>
  );
});

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  description?: string;
  error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(function Textarea(
  { label, description, error, id, className, rows = 4, ...props },
  ref,
) {
  const reactId = useId();
  const fieldId = id ?? reactId;
  return (
    <FieldShell id={fieldId} label={label} description={description} error={error}>
      <textarea
        ref={ref}
        id={fieldId}
        rows={rows}
        aria-invalid={error ? true : undefined}
        className={cn(CONTROL_BASE, "resize-y", className)}
        {...props}
      />
    </FieldShell>
  );
});

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  description?: string;
  error?: string;
  options: { value: string; label: string }[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { label, description, error, id, className, options, ...props },
  ref,
) {
  const reactId = useId();
  const fieldId = id ?? reactId;
  return (
    <FieldShell id={fieldId} label={label} description={description} error={error}>
      <select
        ref={ref}
        id={fieldId}
        aria-invalid={error ? true : undefined}
        className={cn(CONTROL_BASE, className)}
        {...props}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </FieldShell>
  );
});

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(function Checkbox(
  { label, id, className, ...props },
  ref,
) {
  const reactId = useId();
  const fieldId = id ?? reactId;
  return (
    <label htmlFor={fieldId} className="flex items-center gap-2 text-sm text-text">
      <input
        ref={ref}
        id={fieldId}
        type="checkbox"
        className={cn(
          "h-4 w-4 rounded border-border text-accent focus-visible:outline-2 focus-visible:outline-accent",
          className,
        )}
        {...props}
      />
      {label}
    </label>
  );
});

/**
 * Partial-date input accepting json-resume formats: YYYY, YYYY-MM, or YYYY-MM-DD.
 * Invalid partial dates surface an error and are reported via onValidChange(null).
 */
const PARTIAL_DATE_RE = /^\d{4}(-\d{2}(-\d{2})?)?$/;

export function DatePartInput({
  label,
  value,
  onChange,
  error,
  id,
}: {
  label?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  id?: string;
}) {
  const reactId = useId();
  const fieldId = id ?? reactId;
  const invalid = value !== "" && !PARTIAL_DATE_RE.test(value);
  return (
    <Input
      id={fieldId}
      label={label}
      placeholder="YYYY, YYYY-MM or YYYY-MM-DD"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      error={error ?? (invalid ? "Use YYYY, YYYY-MM or YYYY-MM-DD" : undefined)}
      inputMode="numeric"
    />
  );
}

export function isValidPartialDate(value: string): boolean {
  return value === "" || PARTIAL_DATE_RE.test(value);
}
