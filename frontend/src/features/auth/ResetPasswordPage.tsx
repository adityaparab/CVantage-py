import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { z } from "zod";
import { resetPassword } from "@/api/auth";
import { toApiError } from "@/api/errors";
import { Button } from "@/components/ui";
import { AuthShell, FormError } from "@/features/auth/AuthShell";
import { TextField } from "@/lib/forms";

const schema = z.object({
  newPassword: z
    .string()
    .min(8, "At least 8 characters")
    .regex(/[A-Z]/, "Needs an uppercase letter")
    .regex(/[a-z]/, "Needs a lowercase letter")
    .regex(/[0-9]/, "Needs a number"),
});
type Values = z.infer<typeof schema>;

export function ResetPasswordPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const [error, setError] = useState<string>();
  const methods = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { newPassword: "" },
  });

  const onSubmit = methods.handleSubmit(async (values) => {
    setError(undefined);
    try {
      await resetPassword(token, values.newPassword);
      navigate("/login", { replace: true });
    } catch (e) {
      setError(toApiError(e).message);
    }
  });

  return (
    <AuthShell title="Choose a new password">
      {token ? (
        <FormProvider {...methods}>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <FormError message={error} />
            <TextField<Values> name="newPassword" label="New password" type="password" />
            <Button type="submit" loading={methods.formState.isSubmitting}>
              Update password
            </Button>
          </form>
        </FormProvider>
      ) : (
        <p role="alert" className="text-sm text-danger">
          This reset link is missing its token.{" "}
          <Link className="text-accent-text" to="/forgot-password">
            Request a new one
          </Link>
          .
        </p>
      )}
    </AuthShell>
  );
}
