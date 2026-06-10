import { useState } from "react";
import {
  Badge,
  Button,
  Checkbox,
  DatePartInput,
  Drawer,
  EmptyState,
  Input,
  Modal,
  ProgressSteps,
  Select,
  Skeleton,
  Spinner,
  Table,
  Tabs,
  Textarea,
  ThemeToggle,
  Tooltip,
  useToast,
  type SortState,
} from "@/components/ui";

interface DemoRow {
  id: string;
  name: string;
  status: string;
}

const DEMO_ROWS: DemoRow[] = [
  { id: "1", name: "Backend Engineer Resume", status: "completed" },
  { id: "2", name: "Data Scientist Resume", status: "in_progress" },
];

/**
 * Dev-only showcase of the UI kit (issue #65). Lets us eyeball every component
 * in both themes and run axe against the kit.
 */
export function Showcase() {
  const { toast } = useToast();
  const [modalOpen, setModalOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [date, setDate] = useState("2024-03");
  const [sort, setSort] = useState<SortState>({ key: "name", direction: "asc" });

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-8 p-8">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">CVantage UI Kit</h1>
        <ThemeToggle />
      </header>

      <section className="flex flex-wrap items-center gap-3">
        <Button>Primary</Button>
        <Button variant="secondary">Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="danger">Danger</Button>
        <Button loading>Loading</Button>
        <Spinner />
        <Tooltip label="Helpful hint">
          <Button variant="secondary">Hover me</Button>
        </Tooltip>
      </section>

      <section className="flex flex-wrap gap-2">
        <Badge>Neutral</Badge>
        <Badge tone="accent">Accent</Badge>
        <Badge tone="success">Completed</Badge>
        <Badge tone="warn">In progress</Badge>
        <Badge tone="danger">Failed</Badge>
        <Badge tone="info">Info</Badge>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <Input label="Full name" placeholder="Ada Lovelace" />
        <Input label="Email" type="email" error="Enter a valid email" />
        <Select
          label="Role"
          options={[
            { value: "candidate", label: "Candidate" },
            { value: "admin", label: "Admin" },
          ]}
        />
        <DatePartInput label="Start date" value={date} onChange={setDate} />
        <Textarea label="Summary" description="A short professional summary" />
        <Checkbox label="I agree to the terms" />
      </section>

      <section>
        <ProgressSteps
          steps={[
            { label: "Comparing", status: "completed" },
            { label: "Suggestions", status: "in_progress" },
            { label: "Interview Qs", status: "pending" },
          ]}
        />
      </section>

      <section>
        <Tabs
          items={[
            {
              id: "overview",
              label: "Overview",
              content: (
                <Table<DemoRow>
                  columns={[
                    { key: "name", header: "Name", sortable: true, render: (r) => r.name },
                    {
                      key: "status",
                      header: "Status",
                      render: (r) => <Badge tone="accent">{r.status}</Badge>,
                    },
                  ]}
                  rows={DEMO_ROWS}
                  rowKey={(r) => r.id}
                  sort={sort}
                  onSortChange={setSort}
                />
              ),
            },
            {
              id: "empty",
              label: "Empty",
              content: (
                <EmptyState title="Nothing here yet" description="Create your first resume." />
              ),
            },
          ]}
        />
      </section>

      <section className="flex flex-wrap gap-3">
        <Button onClick={() => setModalOpen(true)}>Open modal</Button>
        <Button variant="secondary" onClick={() => setDrawerOpen(true)}>
          Open drawer
        </Button>
        <Button variant="ghost" onClick={() => toast("Saved successfully", "success")}>
          Show toast
        </Button>
      </section>

      <section className="grid gap-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-4 w-1/2" />
      </section>

      <Modal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        title="Confirm action"
        footer={
          <>
            <Button variant="ghost" onClick={() => setModalOpen(false)}>
              Cancel
            </Button>
            <Button onClick={() => setModalOpen(false)}>Confirm</Button>
          </>
        }
      >
        This is an accessible dialog. Press Escape or click the backdrop to close.
      </Modal>

      <Drawer open={drawerOpen} onClose={() => setDrawerOpen(false)} title="Details">
        Slide-over panel content.
      </Drawer>
    </div>
  );
}
