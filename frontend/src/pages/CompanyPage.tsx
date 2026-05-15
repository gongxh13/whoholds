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
      {isLoading && <Skeleton />}
      {error && (
        <div
          style={{
            background: "var(--danger-bg)",
            color: "var(--danger)",
            border: "1px solid var(--danger)",
            padding: "12px 16px",
            borderRadius: "var(--r)",
          }}
        >
          {(error as Error).message}
        </div>
      )}
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

function Skeleton(): JSX.Element {
  return (
    <div>
      <div
        style={{
          width: 240,
          height: 28,
          background: "var(--bg-sunken)",
          borderRadius: 6,
          marginBottom: 24,
        }}
      />
      {Array.from({ length: 8 }, (_, i) => `skel-${i}`).map((id, i) => (
        <div
          key={id}
          style={{
            height: 36,
            background: "var(--bg-sunken)",
            borderRadius: 4,
            marginBottom: 6,
            opacity: 0.4 + (8 - i) / 16,
          }}
        />
      ))}
    </div>
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
      {
        header: "#",
        accessorKey: "rank",
        size: 50,
        cell: (info) => (
          <span
            className="tabular"
            style={{
              fontWeight: 700,
              color: info.row.original.rank <= 3 ? "var(--focus-orange)" : "var(--muted)",
            }}
          >
            {info.row.original.rank}
          </span>
        ),
      },
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
        header: "",
        id: "type",
        size: 60,
        cell: (info) => (
          <span className={info.row.original.is_person ? "pill pill-person" : "pill pill-inst"}>
            {info.row.original.is_person ? "个人" : "机构"}
          </span>
        ),
      },
      {
        header: "股份性质",
        accessorKey: "share_type",
        size: 110,
        cell: (info) => (
          <span className="muted" style={{ fontSize: 12 }}>
            {info.row.original.share_type}
          </span>
        ),
      },
      {
        header: "持股",
        accessorKey: "holdings",
        cell: (info) => <span className="tabular">{formatShares(info.row.original.holdings)}</span>,
      },
      {
        header: "占比",
        accessorKey: "pct",
        cell: (info) => <span className="tabular">{formatPct(info.row.original.pct)}</span>,
      },
      {
        header: "市值",
        accessorKey: "holdings_value",
        cell: (info) => (
          <span className="tabular" style={{ fontWeight: 500 }}>
            {formatYuan(info.row.original.holdings_value ?? null)}
          </span>
        ),
      },
      {
        header: "变动",
        accessorKey: "change_value",
        size: 100,
        cell: (info) => {
          const v = info.row.original.change_value;
          if (!v || v === "不变")
            return (
              <span className="faint" style={{ fontSize: 12 }}>
                —
              </span>
            );
          const isNew = v === "新进";
          const isPositive = v.startsWith("+") || isNew;
          return (
            <span
              className="tabular"
              style={{
                fontSize: 12,
                color: isPositive ? "var(--success)" : "var(--danger)",
                fontWeight: 600,
              }}
            >
              {v}
            </span>
          );
        },
      },
    ],
    [],
  );

  return (
    <div>
      <PageHeader
        title={data.stock_name}
        subtitle={data.stock_code.toUpperCase()}
        right={
          <DateSelect
            value={selectedDate ?? ""}
            onChange={onDateChange}
            options={data.available_dates}
          />
        }
      />

      {data.stack_series.length > 0 && (
        <section className="card" style={{ padding: 20, marginBottom: 24 }}>
          <h2 style={{ marginBottom: 12 }}>持股堆叠时序</h2>
          <EChartsWrapper option={stackOption} height={320} />
        </section>
      )}

      <section className="card" style={{ padding: 20 }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginBottom: 12,
          }}
        >
          <h2 style={{ margin: 0 }}>前十大股东</h2>
          <span className="faint" style={{ fontSize: 12 }}>
            截至 {formatDate(selectedDate)}
          </span>
        </header>
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

function PageHeader({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle: string;
  right?: React.ReactNode;
}): JSX.Element {
  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "baseline",
        marginBottom: 24,
        gap: 16,
        flexWrap: "wrap",
      }}
    >
      <div>
        <h1 style={{ marginBottom: 2 }}>{title}</h1>
        <code style={{ fontSize: 12, color: "var(--muted)" }}>{subtitle}</code>
      </div>
      {right}
    </header>
  );
}

function DateSelect({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}): JSX.Element {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <label htmlFor="report-date" className="muted" style={{ fontSize: 12 }}>
        报告期
      </label>
      <select
        id="report-date"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="input"
      >
        {options.map((d) => (
          <option key={d} value={d}>
            {formatDate(d)}
          </option>
        ))}
      </select>
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
      areaStyle: { opacity: 0.85 },
      smooth: true,
      symbol: "none",
      lineStyle: { width: 0.5 },
      data: dates.map((d) => byKey.get(`${d}|${h}`) ?? 0),
    }));
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: "var(--bg-elev)",
        borderColor: "var(--line)",
        textStyle: { color: "var(--fg)", fontSize: 12 },
      },
      legend: { type: "scroll", bottom: 0, textStyle: { color: "var(--muted)", fontSize: 11 } },
      grid: { left: 60, right: 20, top: 20, bottom: 50 },
      xAxis: {
        type: "category",
        data: dates.map(formatDate),
        axisLine: { lineStyle: { color: "var(--chart-grid)" } },
        axisLabel: { color: "var(--muted)", fontSize: 11 },
      },
      yAxis: {
        type: "value",
        name: "持股 (股)",
        nameTextStyle: { color: "var(--muted)" },
        splitLine: { lineStyle: { color: "var(--chart-grid)" } },
        axisLabel: { color: "var(--muted)", fontSize: 11 },
      },
      series,
    };
  }, [data]);
}
