import { Controller, useFormContext, type FieldValues, type Path } from "react-hook-form";
import { Checkbox, DatePartInput, Input, Select, Textarea } from "@/components/ui";

interface BaseFieldProps<T extends FieldValues> {
  name: Path<T>;
  label?: string;
  description?: string;
  placeholder?: string;
}

/** Text input bound to react-hook-form context with accessible label/error. */
export function TextField<T extends FieldValues>({
  name,
  label,
  description,
  placeholder,
  type = "text",
}: BaseFieldProps<T> & { type?: string }) {
  const { register, getFieldState, formState } = useFormContext<T>();
  const { error } = getFieldState(name, formState);
  return (
    <Input
      label={label}
      description={description}
      placeholder={placeholder}
      type={type}
      error={error?.message}
      {...register(name)}
    />
  );
}

export function TextareaField<T extends FieldValues>({
  name,
  label,
  description,
  placeholder,
  rows,
}: BaseFieldProps<T> & { rows?: number }) {
  const { register, getFieldState, formState } = useFormContext<T>();
  const { error } = getFieldState(name, formState);
  return (
    <Textarea
      label={label}
      description={description}
      placeholder={placeholder}
      rows={rows}
      error={error?.message}
      {...register(name)}
    />
  );
}

export function SelectField<T extends FieldValues>({
  name,
  label,
  options,
}: BaseFieldProps<T> & { options: { value: string; label: string }[] }) {
  const { register, getFieldState, formState } = useFormContext<T>();
  const { error } = getFieldState(name, formState);
  return <Select label={label} options={options} error={error?.message} {...register(name)} />;
}

export function CheckboxField<T extends FieldValues>({
  name,
  label,
}: {
  name: Path<T>;
  label: string;
}) {
  const { register } = useFormContext<T>();
  return <Checkbox label={label} {...register(name)} />;
}

/** Partial-date field (YYYY / YYYY-MM / YYYY-MM-DD), controlled for the custom input. */
export function DateField<T extends FieldValues>({ name, label }: BaseFieldProps<T>) {
  const { control, getFieldState, formState } = useFormContext<T>();
  const { error } = getFieldState(name, formState);
  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <DatePartInput
          label={label}
          value={(field.value as string) ?? ""}
          onChange={field.onChange}
          error={error?.message}
        />
      )}
    />
  );
}
