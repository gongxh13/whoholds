import { AppShell } from "@/components/AppShell";
import { DataTable } from "@/components/DataTable";
import { EChartsWrapper } from "@/components/EChartsWrapper";
import { type CompanyDetail, type Top10Row, getCompany } from "@/lib/api";
import { formatDate, formatPct, formatShares, formatYuan } from "@/lib/format";
import type { RouteParams } from "@/lib/router";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo, useState } from "react";

export function CompanyPage({ params }: { params: RouteParams }): JSX.Element {
  const code = params.code ?? "";
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ["company", code, selectedDate],
    queryFn: () => getCompany(code, selectedDate ?? undefined),
  });

  return (
    <AppShell>
      {isLoading && <p style={{ color: "var(--muted)" }}>加载中…</p>}
      {error && <p style={{ color: "#c0392b" }}>{(error as Error).message}</p>}
      {data && (
        <Body
          data={data}
          selectedDate={selectedDate ?? data.current_date ?? null}
          onDateChange={setSelectedDate}
        />
      )}
    </AppShell>
  );
}

function Body({
  data,
  selectedDate,
  onDateChange,
}: {
  data: CompanyDetail;
  selectedDate: string | null;
  onDateChange: (d: string) => void;
}): JSX.Element {
  const stackOption = useStackOption(data);

  const columns = useMemo<ColumnDef<Top10Row, unknown>[]>(
    () => [
      { header: "名次", accessorKey: "rank", size: 60 },
      {
        header: "股东",
        accessorKey: "holder_name",
        cell: (info) => {
          const row = info.row.original;
          if (row.is_person) {
            return <a href={`#/p/${encodeURIComponent(row.holder_name)}`}>{row.holder_name}</a>;
          }
          return row.holder_name;
        },
      },
      {
        header: "类型",
        cell: (info) => (info.row.original.is_person ? "个人" : "机构"),
        size: 70,
      },
      { header: "股份性质", accessorKey: "share_type", size: 110 },
      {
        header: "持股",
        accessorKey: "holdings",
        cell: (info) => formatShares(info.row.original.holdings),
      },
      {
        header: "占比",
        accessorKey: "pct",
        cell: (info) => formatPct(info.row.original.pct),
      },
      {
        header: "市值",
        accessorKey: "holdings_value",
        cell: (info) => formatYuan(info.row.original.holdings_value ?? null),
      },
      {
        header: "变动",
        accessorKey: "change_value",
        cell: (info) => info.row.original.change_value ?? "—",
        size: 100,
      },
    ],
    [],
  );

  return (
    <div>
      <h1 style={{ marginTop: 0 }}>
        {data.stock_name}{" "}
        <span style={{ color: "var(--muted)", fontSize: 14 }}>{data.stock_code}</span>
      </h1>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
        <label htmlFor="report-date" style={{ color: "var(--muted)", fontSize: 13 }}>
          报告期
        </label>
        <select
          id="report-date"
          value={selectedDate ?? ""}
          onChange={(e) => onDateChange(e.target.value)}
          style={selectStyle}
        >
          {data.available_dates.map((d) => (
            <option key={d} value={d}>
              {formatDate(d)}
            </option>
          ))}
        </select>
      </div>

      {data.stack_series.length > 0 && (
        <section style={{ marginBottom: 24 }}>
          <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>持股堆叠时序</h2>
          <EChartsWrapper option={stackOption} height={300} />
        </section>
      )}

      <section>
        <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>
          前十大股东 · {formatDate(selectedDate)}
        </h2>
        <DataTable
          data={data.top10}
          columns={columns}
          urlKey="t"
          defaultSort={[{ id: "rank", desc: false }]}
        />
      </section>
    </div>
  );
}

function useStackOption(data: CompanyDetail) {
  return useMemo(() => {
    const dates = Array.from(new Set(data.stack_series.map((s) => s.date))).sort();
    const holders = Array.from(new Set(data.stack_series.map((s) => s.holder_name)));
    const byKey = new Map<string, number>();
    for (const s of data.stack_series) byKey.set(`${s.date}|${s.holder_name}`, s.holdings);
    const series = holders.map((h) => ({
      name: h,
      type: "line",
      stack: "all",
      areaStyle: {},
      smooth: true,
      symbol: "none",
      data: dates.map((d) => byKey.get(`${d}|${h}`) ?? 0),
    }));
    return {
      tooltip: { trigger: "axis" },
      legend: { type: "scroll", bottom: 0 },
      grid: { left: 50, right: 20, top: 20, bottom: 60 },
      xAxis: { type: "category", data: dates.map(formatDate) },
      yAxis: { type: "value", name: "持股 (股)" },
      series,
    };
  }, [data]);
}

const selectStyle: React.CSSProperties = {
  background: "var(--bg-elev)",
  border: "1px solid var(--line)",
  color: "var(--fg)",
  padding: "4px 8px",
  borderRadius: 6,
};
