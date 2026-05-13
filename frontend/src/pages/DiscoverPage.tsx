import { AppShell } from "@/components/AppShell";
import { DataTable } from "@/components/DataTable";
import {
  type CoholderPair,
  type CrossHolder,
  getTopCoholderPairs,
  getTopCrossHolders,
} from "@/lib/api";
import { formatYuan } from "@/lib/format";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

export function DiscoverPage(): JSX.Element {
  const crossQ = useQuery({
    queryKey: ["discover", "cross"],
    queryFn: () => getTopCrossHolders(50),
  });
  const pairsQ = useQuery({
    queryKey: ["discover", "pairs"],
    queryFn: () => getTopCoholderPairs(50, 3),
  });

  const crossCols = useMemo<ColumnDef<CrossHolder, unknown>[]>(
    () => [
      {
        header: "股东",
        accessorKey: "holder_name",
        cell: (info) => (
          <a href={`#/p/${encodeURIComponent(info.row.original.holder_name)}`}>
            {info.row.original.holder_name}
          </a>
        ),
      },
      {
        header: "公司数",
        accessorKey: "n_companies",
        cell: (info) => info.row.original.n_companies,
      },
      {
        header: "总市值",
        accessorKey: "total_value",
        cell: (info) => formatYuan(info.row.original.total_value ?? null),
      },
      {
        header: "示例公司",
        cell: (info) =>
          info.row.original.companies
            .slice(0, 5)
            .map((c) => c.stock_name)
            .join("、"),
      },
    ],
    [],
  );

  const pairCols = useMemo<ColumnDef<CoholderPair, unknown>[]>(
    () => [
      {
        header: "股东 A",
        accessorKey: "holder_a",
        cell: (info) => (
          <a href={`#/p/${encodeURIComponent(info.row.original.holder_a)}`}>
            {info.row.original.holder_a}
          </a>
        ),
      },
      {
        header: "股东 B",
        accessorKey: "holder_b",
        cell: (info) => (
          <a href={`#/p/${encodeURIComponent(info.row.original.holder_b)}`}>
            {info.row.original.holder_b}
          </a>
        ),
      },
      { header: "共同公司数", accessorKey: "co_count" },
      {
        header: "示例",
        cell: (info) => {
          const segs = info.row.original.company_list
            .split(",")
            .slice(0, 3)
            .map((s) => s.split("|")[1] ?? s);
          return segs.join("、");
        },
      },
    ],
    [],
  );

  return (
    <AppShell>
      <h1 style={{ marginTop: 0 }}>发现</h1>
      <p style={{ color: "var(--muted)" }}>
        全市场预聚合 — design.md §三铁律 之"全市场分析后端预聚合"。
      </p>

      <section style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>跨持股 个人股东榜</h2>
        {crossQ.isLoading && <p>加载中…</p>}
        {crossQ.error && <p style={{ color: "#c0392b" }}>{(crossQ.error as Error).message}</p>}
        {crossQ.data && (
          <DataTable
            data={crossQ.data}
            columns={crossCols}
            urlKey="cx"
            defaultSort={[{ id: "n_companies", desc: true }]}
            pageSize={20}
          />
        )}
      </section>

      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>协同股东对榜</h2>
        {pairsQ.isLoading && <p>加载中…</p>}
        {pairsQ.error && <p style={{ color: "#c0392b" }}>{(pairsQ.error as Error).message}</p>}
        {pairsQ.data && (
          <DataTable
            data={pairsQ.data}
            columns={pairCols}
            urlKey="cp"
            defaultSort={[{ id: "co_count", desc: true }]}
            pageSize={20}
          />
        )}
      </section>
    </AppShell>
  );
}
