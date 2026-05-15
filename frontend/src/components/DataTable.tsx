/* TanStack-table-based sortable + paged table.
   Sort + page state are persisted into the URL hash query string so links and
   refresh keep the user where they were — per design.md §"服务端排序 / 分页
   通过 URL query 参数". */
import {
  type ColumnDef,
  type SortingState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { useEffect, useState } from "react";

type Props<T extends object> = {
  data: T[];
  columns: ColumnDef<T, unknown>[];
  pageSize?: number;
  urlKey?: string;
  defaultSort?: SortingState;
};

export function DataTable<T extends object>({
  data,
  columns,
  pageSize = 20,
  urlKey,
  defaultSort = [],
}: Props<T>): JSX.Element {
  const initial = urlKey ? readUrlState(urlKey) : null;
  const [sorting, setSorting] = useState<SortingState>(initial?.sorting ?? defaultSort);
  const [pageIndex, setPageIndex] = useState(initial?.page ?? 0);

  useEffect(() => {
    if (!urlKey) return;
    // Treat current state as default if it matches `defaultSort` + page 0 —
    // otherwise we'd pollute the URL with the initial sort on every page load.
    const sortingIsDefault =
      sorting.length === defaultSort.length &&
      sorting.every((s, i) => {
        const d = defaultSort[i];
        return d && s.id === d.id && s.desc === d.desc;
      });
    if (sortingIsDefault && pageIndex === 0) {
      writeUrlState(urlKey, null);
    } else {
      writeUrlState(urlKey, { sorting, page: pageIndex });
    }
  }, [urlKey, sorting, pageIndex, defaultSort]);

  const table = useReactTable({
    data,
    columns,
    state: { sorting, pagination: { pageIndex, pageSize } },
    onSortingChange: setSorting,
    onPaginationChange: (updater) => {
      const next = typeof updater === "function" ? updater({ pageIndex, pageSize }) : updater;
      setPageIndex(next.pageIndex);
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const totalPages = Math.max(1, Math.ceil(data.length / pageSize));

  return (
    <div>
      <table style={tableStyle}>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const canSort = h.column.getCanSort();
                const dir = h.column.getIsSorted();
                return (
                  <th
                    key={h.id}
                    onClick={canSort ? h.column.getToggleSortingHandler() : undefined}
                    onKeyDown={
                      canSort
                        ? (e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              h.column.getToggleSortingHandler()?.(e);
                            }
                          }
                        : undefined
                    }
                    tabIndex={canSort ? 0 : -1}
                    style={{
                      ...thStyle,
                      cursor: canSort ? "pointer" : "default",
                      userSelect: "none",
                    }}
                  >
                    {flexRender(h.column.columnDef.header, h.getContext())}
                    {dir === "asc" ? " ▲" : dir === "desc" ? " ▼" : ""}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row, i) => (
            <tr
              key={row.id}
              style={{ background: i % 2 === 0 ? "transparent" : "var(--bg)" }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-hover)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = i % 2 === 0 ? "transparent" : "var(--bg)";
              }}
            >
              {row.getVisibleCells().map((c) => (
                <td key={c.id} style={tdStyle}>
                  {flexRender(c.column.columnDef.cell, c.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.length > pageSize && (
        <div style={pagerStyle}>
          <button
            type="button"
            onClick={() => setPageIndex(0)}
            disabled={pageIndex === 0}
            className="btn"
            style={{ padding: "3px 8px", minWidth: 28 }}
          >
            «
          </button>
          <button
            type="button"
            onClick={() => setPageIndex((p) => Math.max(0, p - 1))}
            disabled={pageIndex === 0}
            className="btn"
            style={{ padding: "3px 8px", minWidth: 28 }}
          >
            ‹
          </button>
          <span className="muted tabular" style={{ fontSize: 12, padding: "0 8px" }}>
            {pageIndex + 1} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => setPageIndex((p) => Math.min(totalPages - 1, p + 1))}
            disabled={pageIndex >= totalPages - 1}
            className="btn"
            style={{ padding: "3px 8px", minWidth: 28 }}
          >
            ›
          </button>
          <button
            type="button"
            onClick={() => setPageIndex(totalPages - 1)}
            disabled={pageIndex >= totalPages - 1}
            className="btn"
            style={{ padding: "3px 8px", minWidth: 28 }}
          >
            »
          </button>
        </div>
      )}
    </div>
  );
}

const tableStyle: React.CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontSize: 13,
};
const thStyle: React.CSSProperties = {
  textAlign: "left",
  padding: "8px 12px",
  borderBottom: "1px solid var(--line)",
  background: "var(--bg-sunken)",
  fontWeight: 600,
  fontSize: 11,
  textTransform: "uppercase",
  letterSpacing: "0.04em",
  color: "var(--muted)",
};
const tdStyle: React.CSSProperties = {
  padding: "10px 12px",
  borderBottom: "1px solid var(--line-muted)",
};
const pagerStyle: React.CSSProperties = {
  display: "flex",
  gap: 4,
  alignItems: "center",
  marginTop: 12,
  justifyContent: "flex-end",
};

type UrlState = { sorting: SortingState; page: number };

function readUrlState(key: string): UrlState | null {
  const hash = window.location.hash.replace(/^#/, "");
  const qIdx = hash.indexOf("?");
  if (qIdx < 0) return null;
  const usp = new URLSearchParams(hash.slice(qIdx + 1));
  const raw = usp.get(key);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UrlState;
  } catch {
    return null;
  }
}

function writeUrlState(key: string, state: UrlState | null): void {
  const hash = window.location.hash.replace(/^#/, "");
  const qIdx = hash.indexOf("?");
  const base = qIdx >= 0 ? hash.slice(0, qIdx) : hash;
  const usp = new URLSearchParams(qIdx >= 0 ? hash.slice(qIdx + 1) : "");
  if (state === null) {
    usp.delete(key);
  } else {
    // URLSearchParams handles percent-encoding — don't encode the JSON twice.
    usp.set(key, JSON.stringify(state));
  }
  const qs = usp.toString();
  const next = qs ? `${base}?${qs}` : base;
  if (window.location.hash !== `#${next}`) {
    window.history.replaceState(null, "", `#${next}`);
  }
}
