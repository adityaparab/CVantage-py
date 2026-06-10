import { zodResolver } from "@hookform/resolvers/zod";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormProvider, useForm, type SubmitHandler } from "react-hook-form";
import { describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { ArrayField, TextField } from "@/lib/forms";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
});
type LoginValues = z.infer<typeof loginSchema>;

function LoginForm({ onSubmit }: { onSubmit: SubmitHandler<LoginValues> }) {
  const methods = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
  });
  return (
    <FormProvider {...methods}>
      <form onSubmit={methods.handleSubmit(onSubmit)}>
        <TextField<LoginValues> name="email" label="Email" />
        <TextField<LoginValues> name="password" label="Password" type="password" />
        <button type="submit">Submit</button>
      </form>
    </FormProvider>
  );
}

interface ListValues {
  items: { value: string }[];
}

function ListForm({ onSubmit }: { onSubmit: SubmitHandler<ListValues> }) {
  const methods = useForm<ListValues>({ defaultValues: { items: [{ value: "" }] } });
  return (
    <FormProvider {...methods}>
      <form onSubmit={methods.handleSubmit(onSubmit)}>
        <ArrayField<ListValues> name="items" newItem={() => ({ value: "" })} addLabel="Add item">
          {(i) => <TextField<ListValues> name={`items.${i}.value`} label={`Item ${i + 1}`} />}
        </ArrayField>
        <button type="submit">Submit</button>
      </form>
    </FormProvider>
  );
}

describe("form fields", () => {
  it("renders zod validation errors accessibly", async () => {
    const user = userEvent.setup();
    render(<LoginForm onSubmit={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "Submit" }));

    const emailError = await screen.findByText("Enter a valid email");
    expect(emailError).toHaveAttribute("role", "alert");
    expect(screen.getByText("Password is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toHaveAttribute("aria-invalid", "true");
  });
});

describe("ArrayField", () => {
  it("adds, reorders, and removes items, round-tripping values", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<ListForm onSubmit={onSubmit} />);

    // Start with 1, add a 2nd.
    await user.click(screen.getByRole("button", { name: "Add item" }));
    let inputs = screen.getAllByRole("textbox");
    expect(inputs).toHaveLength(2);

    await user.type(inputs[0], "alpha");
    await user.type(inputs[1], "beta");

    // Move the first item down → order becomes beta, alpha.
    await user.click(screen.getAllByRole("button", { name: "Move down" })[0]);
    await user.click(screen.getByRole("button", { name: "Submit" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0]).toEqual({
      items: [{ value: "beta" }, { value: "alpha" }],
    });

    // Remove the first item.
    await user.click(screen.getAllByRole("button", { name: "Remove" })[0]);
    inputs = screen.getAllByRole("textbox");
    expect(inputs).toHaveLength(1);
    expect(inputs[0]).toHaveValue("alpha");
  });
});
