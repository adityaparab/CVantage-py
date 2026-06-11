import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FormProvider, useForm } from "react-hook-form";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CheckboxField, DateField, SelectField, TextareaField } from "@/lib/forms";
import { useUnsavedChangesGuard } from "@/lib/forms/useUnsavedChangesGuard";

interface Values {
  role: string;
  agree: boolean;
  startDate: string;
  bio: string;
}

function FieldsForm() {
  const methods = useForm<Values>({
    defaultValues: { role: "a", agree: false, startDate: "", bio: "" },
  });
  return (
    <FormProvider {...methods}>
      <SelectField<Values>
        name="role"
        label="Role"
        options={[
          { value: "a", label: "Candidate" },
          { value: "b", label: "Admin" },
        ]}
      />
      <CheckboxField<Values> name="agree" label="Agree" />
      <DateField<Values> name="startDate" label="Start" />
      <TextareaField<Values> name="bio" label="Bio" />
    </FormProvider>
  );
}

describe("form field bindings", () => {
  it("binds select, checkbox, date, and textarea to the form", async () => {
    const user = userEvent.setup();
    render(<FieldsForm />);
    await user.selectOptions(screen.getByLabelText("Role"), "b");
    await user.click(screen.getByLabelText("Agree"));
    await user.type(screen.getByLabelText("Start"), "2024-03");
    await user.type(screen.getByLabelText("Bio"), "hello");

    expect((screen.getByLabelText("Role") as HTMLSelectElement).value).toBe("b");
    expect(screen.getByLabelText("Agree")).toBeChecked();
    expect(screen.getByLabelText("Start")).toHaveValue("2024-03");
    expect(screen.getByLabelText("Bio")).toHaveValue("hello");
  });
});

describe("useUnsavedChangesGuard", () => {
  afterEach(() => vi.restoreAllMocks());

  it("registers a beforeunload warning while dirty", () => {
    const addSpy = vi.spyOn(window, "addEventListener");
    function Guarded() {
      useUnsavedChangesGuard(true);
      return <p>guarded</p>;
    }
    const router = createMemoryRouter([{ path: "/", element: <Guarded /> }]);
    render(<RouterProvider router={router} />);
    expect(screen.getByText("guarded")).toBeInTheDocument();
    expect(addSpy).toHaveBeenCalledWith("beforeunload", expect.any(Function));
  });
});
