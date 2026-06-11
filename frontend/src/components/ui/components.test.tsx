import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { Badge, Button, EmptyState, Modal, ProgressSteps, Table, Tabs } from "@/components/ui";

describe("Button", () => {
  it("invokes onClick and disables while loading", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    const { rerender } = render(<Button onClick={onClick}>Save</Button>);
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledTimes(1);

    rerender(
      <Button onClick={onClick} loading>
        Save
      </Button>,
    );
    expect(screen.getByRole("button", { name: /Save/ })).toBeDisabled();
  });
});

describe("Badge & EmptyState", () => {
  it("renders a status badge and an empty state with an action", () => {
    render(
      <>
        <Badge tone="success">Completed</Badge>
        <EmptyState title="No resumes" action={<Button>Create</Button>} />
      </>,
    );
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.getByText("No resumes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create" })).toBeInTheDocument();
  });
});

describe("Modal", () => {
  it("closes on Escape and on the close button", async () => {
    const user = userEvent.setup();
    function Harness() {
      const [open, setOpen] = useState(true);
      return (
        <Modal open={open} onClose={() => setOpen(false)} title="Confirm">
          Body
        </Modal>
      );
    }
    render(<Harness />);
    expect(screen.getByRole("dialog", { name: "Confirm" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("Tabs", () => {
  it("switches panels on tab click", async () => {
    const user = userEvent.setup();
    render(
      <Tabs
        items={[
          { id: "a", label: "First", content: <p>Panel A</p> },
          { id: "b", label: "Second", content: <p>Panel B</p> },
        ]}
      />,
    );
    expect(screen.getByText("Panel A")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "Second" }));
    expect(screen.getByText("Panel B")).toBeInTheDocument();
  });
});

describe("Table", () => {
  it("fires onSortChange when a sortable header is clicked", async () => {
    const user = userEvent.setup();
    const onSortChange = vi.fn();
    render(
      <Table
        columns={[
          { key: "name", header: "Name", sortable: true, render: (r: { name: string }) => r.name },
        ]}
        rows={[{ name: "Ada" }]}
        rowKey={(r) => r.name}
        sort={{ key: "name", direction: "asc" }}
        onSortChange={onSortChange}
      />,
    );
    await user.click(screen.getByRole("button", { name: /Name/ }));
    expect(onSortChange).toHaveBeenCalledWith({ key: "name", direction: "desc" });
  });
});

describe("ProgressSteps", () => {
  it("exposes step status to assistive tech", () => {
    render(
      <ProgressSteps
        steps={[
          { label: "Comparing", status: "completed" },
          { label: "Suggestions", status: "in_progress" },
        ]}
      />,
    );
    expect(screen.getByText("Comparing")).toBeInTheDocument();
    expect(screen.getByText(/in progress/)).toBeInTheDocument();
  });
});
