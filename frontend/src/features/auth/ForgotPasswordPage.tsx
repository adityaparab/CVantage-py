import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { Link } from "react-router-dom";
import { z } from "zod";
import { forgotPassword } from "@/api/auth";
import { toApiError } from "@/api/errors";
import { Button } from "@/components/ui";
import { AuthShell, FormError } from "@/features/auth/AuthShell";
import { TextField } from "@/lib/forms";

const schema = z.object({ email: z.string().email("Enter a valid email") });
type Values = z.infer<typeof schema>;

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string>();
  const methods = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { email: "" } });

  const onSubmit = methods.handleSubmit(async (values) => {
    setError(undefined);
    try {
      await forgotPassword(values.email);
      setSent(true);
    } catch (e) {
      setError(toApiError(e).message);
    }
  });

  return (
    <AuthShell
      title="Reset your password"
      subtitle="We’ll email you a reset link if an account exists."
      footer={
        <Link className="font-medium text-accent-text" to="/login">
          Back to log in
        </Link>
      }
    >
      {sent ? (
        <p role="status" className="rounded-md bg-success-bg px-3 py-2 text-sm text-success">
          If that email is registered, a reset link is on its way.
        </p>
      ) : (
        <FormProvider {...methods}>
          <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
            <FormError message={error} />
            <TextField<Values> name="email" label="Email" type="email" />
            <Button type="submit" loading={methods.formState.isSubmitting}>
              Send reset link
            </Button>
          </form>
        </FormProvider>
      )}
    </AuthShell>
  );
}
