import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import {
  Checkbox,
  DatePartInput,
  Drawer,
  Input,
  Select,
  Skeleton,
  Spinner,
  Table,
  Textarea,
  Tooltip,
} from "@/components/ui";

describe("form controls", () => {
  it("associates labels, descriptions, and errors", () => {
    render(
      <Input label="Email" description="We never share it" error="Required" defaultValue="x" />,
    );
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("We never share it")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
  });

  it("renders select options, a checkbox, and a textarea", async () => {
    const user = userEvent.setup();
    render(
      <>
        <Select
          label="Role"
          options={[
            { value: "a", label: "Candidate" },
            { value: "b", label: "Admin" },
          ]}
        />
        <Checkbox label="Agree" />
        <Textarea label="Bio" />
      </>,
    );
    await user.selectOptions(screen.getByLabelText("Role"), "b");
    expect((screen.getByLabelText("Role") as HTMLSelectElement).value).toBe("b");
    await user.click(screen.getByLabelText("Agree"));
    expect(screen.getByLabelText("Agree")).toBeChecked();
    expect(screen.getByLabelText("Bio")).toBeInTheDocument();
  });

  it("validates partial dates", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [v, setV] = useState("");
      return <DatePartInput label="Start" value={v} onChange={setV} />;
    }
    render(<Harness />);
    await user.type(screen.getByLabelText("Start"), "13/2024");
    expect(screen.getByRole("alert")).toHaveTextContent(/YYYY/);
  });
});

describe("misc components", () => {
  it("renders spinner, skeleton, and an empty table", () => {
    render(
      <>
        <Spinner />
        <Skeleton className="h-4 w-10" />
        <Table
          columns={[{ key: "n", header: "Name", render: (r: { n: string }) => r.n }]}
          rows={[]}
          rowKey={(r) => r.n}
          emptyMessage="Nothing here"
        />
      </>,
    );
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });

  it("shows a tooltip label and an open drawer", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <>
          <Tooltip label="Hint">
            <button onClick={() => setOpen(true)}>Open</button>
          </Tooltip>
          <Drawer open={open} onClose={() => setOpen(false)} title="Side panel">
            Drawer body
          </Drawer>
        </>
      );
    }
    render(<Harness />);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Hint");
    await user.click(screen.getByRole("button", { name: "Open" }));
    expect(screen.getByRole("dialog", { name: "Side panel" })).toBeInTheDocument();
  });
});
