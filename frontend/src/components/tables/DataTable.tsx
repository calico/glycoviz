import { useCallback, useMemo, useState } from "react";

// ── Public types ────────────────────────────────────────────────────────────

export interface Column<T> {
  key: keyof T & string;
  label: string;
  sortable?: boolean;
  render?: (value: T[keyof T], row: T) => React.ReactNode;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  onRowClick?: (row: T) => void;
  selectable?: boolean;
  onSelectionChange?: (selected: T[]) => void;
  exportFilename?: string;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

type SortDir = "asc" | "desc";

function defaultCompare<T>(a: T, b: T, key: keyof T): number {
  const va = a[key];
  const vb = b[key];
  if (va == null && vb == null) return 0;
  if (va == null) return -1;
  if (vb == null) return 1;
  if (typeof va === "number" && typeof vb === "number") return va - vb;
  return String(va).localeCompare(String(vb));
}

function toCsvValue(val: unknown): string {
  if (val == null) return "";
  const str = String(val);
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

// ── Component ───────────────────────────────────────────────────────────────

export function DataTable<T extends Record<string, unknown>>({
  columns,
  data,
  onRowClick,
  selectable = false,
  onSelectionChange,
  exportFilename,
}: DataTableProps<T>) {
  // Sort state
  const [sortKey, setSortKey] = useState<(keyof T & string) | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // Selection state (track by index for identity)
  const [selectedIndices, setSelectedIndices] = useState<Set<number>>(
    new Set(),
  );

  // Sorted data
  const sortedData = useMemo(() => {
    if (!sortKey) return data;
    const dir = sortDir === "asc" ? 1 : -1;
    return [...data].sort((a, b) => dir * defaultCompare(a, b, sortKey));
  }, [data, sortKey, sortDir]);

  // Handle header click
  const handleSort = useCallback(
    (key: keyof T & string) => {
      if (sortKey === key) {
        setSortDir((d) => (d === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey],
  );

  // Selection helpers
  const toggleRow = useCallback(
    (index: number) => {
      setSelectedIndices((prev) => {
        const next = new Set(prev);
        if (next.has(index)) {
          next.delete(index);
        } else {
          next.add(index);
        }
        onSelectionChange?.([...next].map((i) => sortedData[i]));
        return next;
      });
    },
    [onSelectionChange, sortedData],
  );

  const toggleAll = useCallback(() => {
    if (selectedIndices.size === sortedData.length) {
      setSelectedIndices(new Set());
      onSelectionChange?.([]);
    } else {
      const all = new Set(sortedData.map((_, i) => i));
      setSelectedIndices(all);
      onSelectionChange?.([...sortedData]);
    }
  }, [selectedIndices.size, sortedData, onSelectionChange]);

  // CSV export
  const handleExport = useCallback(() => {
    const header = columns.map((c) => toCsvValue(c.label)).join(",");
    const rows = sortedData.map((row) =>
      columns.map((c) => toCsvValue(row[c.key])).join(","),
    );
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = exportFilename ?? "export.csv";
    link.click();
    URL.revokeObjectURL(url);
  }, [columns, sortedData, exportFilename]);

  // Sort indicator
  const sortIndicator = (key: keyof T & string) => {
    if (sortKey !== key) return null;
    return sortDir === "asc" ? " ▲" : " ▼";
  };

  return (
    <div className="w-full">
      {/* Toolbar */}
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm text-gray-500">
          {sortedData.length} row{sortedData.length !== 1 ? "s" : ""}
          {selectable && selectedIndices.size > 0 && (
            <span className="ml-2 font-medium text-blue-600">
              ({selectedIndices.size} selected)
            </span>
          )}
        </p>
        {exportFilename && (
          <button
            type="button"
            onClick={handleExport}
            className="inline-flex items-center gap-1 rounded bg-white px-3 py-1.5 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-300 hover:bg-gray-50"
          >
            <svg
              className="h-4 w-4"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12m0 0l-4-4m4 4l4-4"
              />
            </svg>
            Export CSV
          </button>
        )}
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              {selectable && (
                <th className="w-10 px-3 py-3">
                  <input
                    type="checkbox"
                    checked={
                      sortedData.length > 0 &&
                      selectedIndices.size === sortedData.length
                    }
                    onChange={toggleAll}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    aria-label="Select all rows"
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  scope="col"
                  className={`px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500 ${
                    col.sortable !== false
                      ? "cursor-pointer select-none hover:text-gray-700"
                      : ""
                  }`}
                  onClick={
                    col.sortable !== false
                      ? () => handleSort(col.key)
                      : undefined
                  }
                >
                  {col.label}
                  {col.sortable !== false && sortIndicator(col.key)}
                </th>
              ))}
            </tr>
          </thead>

          <tbody className="divide-y divide-gray-100 bg-white">
            {sortedData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length + (selectable ? 1 : 0)}
                  className="px-4 py-8 text-center text-sm text-gray-400"
                >
                  No data available
                </td>
              </tr>
            ) : (
              sortedData.map((row, idx) => (
                <tr
                  key={idx}
                  onClick={() => onRowClick?.(row)}
                  className={`
                    ${onRowClick ? "cursor-pointer" : ""}
                    ${selectedIndices.has(idx) ? "bg-blue-50" : "hover:bg-gray-50"}
                    transition-colors
                  `}
                >
                  {selectable && (
                    <td className="w-10 px-3 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIndices.has(idx)}
                        onChange={(e) => {
                          e.stopPropagation();
                          toggleRow(idx);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                        aria-label={`Select row ${idx + 1}`}
                      />
                    </td>
                  )}
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className="whitespace-nowrap px-4 py-3 text-sm text-gray-700"
                    >
                      {col.render
                        ? col.render(row[col.key], row)
                        : String(row[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
