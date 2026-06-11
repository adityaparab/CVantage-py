import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toApiError } from "@/api/errors";
import { Button } from "@/components/ui";
import { AuthShell, FormError } from "@/features/auth/AuthShell";
import { OAuthButtons } from "@/features/auth/OAuthButtons";
import { loginSchema, type LoginValues } from "@/features/auth/schemas";
import { useAuth } from "@/lib/auth";
import { TextField } from "@/lib/forms";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string>();
  const methods = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });

  const from =
    (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/dashboard";

  const onSubmit = methods.handleSubmit(async (values) => {
    setError(undefined);
    try {
      await login(values);
      navigate(from, { replace: true });
    } catch (e) {
      setError(toApiError(e).message);
    }
  });

  return (
    <AuthShell
      title="Log in"
      footer={
        <>
          Need an account?{" "}
          <Link className="font-medium text-accent-text" to="/register">
            Sign up
          </Link>
        </>
      }
    >
      <FormProvider {...methods}>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <FormError message={error} />
          <TextField<LoginValues> name="email" label="Email" type="email" />
          <TextField<LoginValues> name="password" label="Password" type="password" />
          <div className="text-right text-sm">
            <Link to="/forgot-password" className="text-accent-text">
              Forgot password?
            </Link>
          </div>
          <Button type="submit" loading={methods.formState.isSubmitting}>
            Log in
          </Button>
        </form>
        <OAuthButtons />
      </FormProvider>
    </AuthShell>
  );
}
