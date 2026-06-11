import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { FormProvider, useForm } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";
import { toApiError } from "@/api/errors";
import { Button } from "@/components/ui";
import { AuthShell, FormError } from "@/features/auth/AuthShell";
import { OAuthButtons } from "@/features/auth/OAuthButtons";
import { passwordStrength, registerSchema, type RegisterValues } from "@/features/auth/schemas";
import { useAuth } from "@/lib/auth";
import { TextField } from "@/lib/forms";

const STRENGTH_LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"];
const STRENGTH_COLORS = ["bg-danger", "bg-danger", "bg-warn", "bg-info", "bg-success"];

function PasswordMeter({ password }: { password: string }) {
  const score = passwordStrength(password);
  if (!password) return null;
  return (
    <div aria-live="polite">
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className={`h-1 flex-1 rounded-full ${i < score ? STRENGTH_COLORS[score] : "bg-border"}`}
          />
        ))}
      </div>
      <p className="mt-1 text-xs text-muted">Password strength: {STRENGTH_LABELS[score]}</p>
    </div>
  );
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState<string>();
  const methods = useForm<RegisterValues>({
    resolver: zodResolver(registerSchema),
    defaultValues: { fullName: "", email: "", password: "" },
  });
  const password = methods.watch("password");

  const onSubmit = methods.handleSubmit(async (values) => {
    setError(undefined);
    try {
      await register(values);
      navigate("/dashboard", { replace: true });
    } catch (e) {
      setError(toApiError(e).message);
    }
  });

  return (
    <AuthShell
      title="Create your account"
      footer={
        <>
          Already have an account?{" "}
          <Link className="font-medium text-accent-text" to="/login">
            Log in
          </Link>
        </>
      }
    >
      <FormProvider {...methods}>
        <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
          <FormError message={error} />
          <TextField<RegisterValues> name="fullName" label="Full name" />
          <TextField<RegisterValues> name="email" label="Email" type="email" />
          <TextField<RegisterValues> name="password" label="Password" type="password" />
          <PasswordMeter password={password} />
          <Button type="submit" loading={methods.formState.isSubmitting}>
            Create account
          </Button>
        </form>
        <OAuthButtons />
      </FormProvider>
    </AuthShell>
  );
}
