import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface Column<Row> {
  key: string;
  header: string;
  sortable?: boolean;
  render: (row: Row) => ReactNode;
  className?: string;
}

export interface SortState {
  key: string;
  direction: "asc" | "desc";
}

export function Table<Row>({
  columns,
  rows,
  rowKey,
  sort,
  onSortChange,
  emptyMessage = "No data",
}: {
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string;
  sort?: SortState;
  onSortChange?: (sort: SortState) => void;
  emptyMessage?: string;
}) {
  const toggleSort = (key: string) => {
    if (!onSortChange) return;
    const direction = sort?.key === key && sort.direction === "asc" ? "desc" : "asc";
    onSortChange({ key, direction });
  };

  return (
    <div className="overflow-x-auto rounded-card border border-border">
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-bg/40">
            {columns.map((col) => {
              const isSorted = sort?.key === col.key;
              return (
                <th
                  key={col.key}
                  scope="col"
                  aria-sort={
                    isSorted ? (sort.direction === "asc" ? "ascending" : "descending") : undefined
                  }
                  className={cn("px-4 py-3 font-semibold text-muted", col.className)}
                >
                  {col.sortable ? (
                    <button
                      type="button"
                      onClick={() => toggleSort(col.key)}
                      className="inline-flex items-center gap-1 hover:text-text focus-visible:outline-2 focus-visible:outline-accent"
                    >
                      {col.header}
                      <span aria-hidden="true">
                        {isSorted ? (sort.direction === "asc" ? "▲" : "▼") : "↕"}
                      </span>
                    </button>
                  ) : (
                    col.header
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-muted">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                className="border-b border-border last:border-0 hover:bg-accent-soft/40"
              >
                {columns.map((col) => (
                  <td key={col.key} className={cn("px-4 py-3 text-text", col.className)}>
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
