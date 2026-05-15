import { AppShell } from "@/components/AppShell";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { DataTable } from "@/components/DataTable";
import { EChartsWrapper } from "@/components/EChartsWrapper";
import {
  type CoholderSummary,
  type CompanyHolding,
  type DisambiguateResponse,
  type PersonDetail,
  getDisambiguate,
  getPerson,
} from "@/lib/api";
import { formatDate, formatPct, formatShares, formatYuan } from "@/lib/format";
import type { RouteParams } from "@/lib/router";
import { useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { useMemo } from "react";

export function PersonPage({ params }: { params: RouteParams }): JSX.Element {
  const name = params.name ?? "";
  const bucketStr = params.bucket;
  const bucket = bucketStr ? Number.parseInt(bucketStr, 10) : undefined;
  const disambiguateQ = useQuery({
    queryKey: ["disambiguate", name],
    queryFn: () => getDisambiguate(name),
    retry: 0,
  });

  return (
    <AppShell>
      {disambiguateQ.isLoading && <Loading />}
      {disambiguateQ.error && <PersonEntity name={name} bucket={bucket} disambiguate={null} />}
      {disambiguateQ.data && <Route data={disambiguateQ.data} name={name} bucket={bucket} />}
    </AppShell>
  );
}

function Loading(): JSX.Element {
  return <p className="muted">加载中…</p>;
}

function Route({
  data,
  name,
  bucket,
}: {
  data: DisambiguateResponse;
  name: string;
  bucket: number | undefined;
}): JSX.Element {
  if (bucket != null) {
    return <PersonEntity name={name} bucket={bucket} disambiguate={data} />;
  }
  if (data.multi_company_buckets <= 1) {
    return <PersonEntity name={name} bucket={undefined} disambiguate={data} />;
  }
  return <PersonHub data={data} />;
}

function PersonHub({ data }: { data: DisambiguateResponse }): JSX.Element {
  return (
    <div>
      <header
        style={{
          marginBottom: 24,
          padding: "var(--s-5)",
          background: "var(--bg-elev)",
          border: "1px solid var(--line)",
          borderRadius: "var(--r-lg)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          aria-hidden
          style={{ position: "absolute", inset: 0, background: "var(--focus-grad)" }}
        />
        <div style={{ position: "relative" }}>
          <div
            style={{
              display: "inline-flex",
              padding: "3px 10px",
              borderRadius: "var(--r-pill)",
              background: "var(--warn-bg)",
              color: "var(--warn)",
              fontSize: 11,
              fontWeight: 600,
              marginBottom: 10,
            }}
          >
            ⚠ 同名拆分中
          </div>
          <h1>{data.name}</h1>
          <p className="muted" style={{ marginTop: 6, maxWidth: 720 }}>
            在 <b style={{ color: "var(--fg)" }}>{data.total_companies}</b> 家公司被披露为前十大股东
            — Layer-2 拓扑算法推断为 <b style={{ color: "var(--fg)" }}>{data.total_buckets}</b>{" "}
            个候选实体（
            {data.multi_company_buckets} 个多公司桶 + {data.singletons} 个单飞）。
            下面每张卡片是一个候选实体。
          </p>
        </div>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
          gap: 14,
        }}
      >
        {data.buckets.map((b) => (
          <a
            key={b.bucket_idx}
            href={`#/p/${encodeURIComponent(data.name)}/${b.bucket_idx}`}
            className="card card-hover"
            style={{
              padding: 16,
              display: "block",
              color: "var(--fg)",
              textDecoration: "none",
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                marginBottom: 6,
                gap: 8,
              }}
            >
              <strong>
                {data.name}
                <span className="muted" style={{ fontWeight: 400 }}>
                  {" "}
                  · #{b.bucket_idx}
                </span>
              </strong>
              <ConfidenceBadge level={b.level} label={b.label} />
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              {b.evidence}
            </div>
            <div
              style={{
                display: "flex",
                gap: 12,
                fontSize: 12,
                marginTop: 12,
                paddingTop: 12,
                borderTop: "1px solid var(--line-muted)",
              }}
            >
              <Stat label="公司" value={`${b.size} 家`} />
              {b.top_peers.length > 0 && (
                <Stat label="常见协同" value={b.top_peers.slice(0, 3).join(" / ")} />
              )}
            </div>
          </a>
        ))}
      </div>

      {data.singletons > 0 && (
        <section className="card" style={{ marginTop: 24, padding: 20 }}>
          <h2 style={{ marginBottom: 12 }}>单飞桶预览 · 前 {Math.min(30, data.singletons)}</h2>
          <p className="muted" style={{ fontSize: 12, marginBottom: 12 }}>
            这些公司里 {data.name} 没和其他个人股东协同 — 大概率不同人或单飞。
          </p>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))",
              gap: 6,
            }}
          >
            {data.singletons_preview.map((s) => (
              <a
                key={s.stock_code}
                href={`#/c/${s.stock_code}`}
                style={{
                  padding: "4px 8px",
                  background: "var(--bg-sunken)",
                  borderRadius: "var(--r-sm)",
                  fontSize: 12,
                  color: "var(--fg)",
                  textDecoration: "none",
                }}
              >
                {s.stock_name}
              </a>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <span className="muted">
      <span className="faint">{label}:</span> <span style={{ color: "var(--fg)" }}>{value}</span>
    </span>
  );
}

function PersonEntity({
  name,
  bucket,
  disambiguate,
}: {
  name: string;
  bucket: number | undefined;
  disambiguate: DisambiguateResponse | null;
}): JSX.Element {
  const personQ = useQuery({
    queryKey: ["person", name, bucket],
    queryFn: () => getPerson(name, bucket),
  });

  if (personQ.isLoading) return <Loading />;
  if (personQ.error)
    return (
      <div
        style={{
          background: "var(--danger-bg)",
          color: "var(--danger)",
          border: "1px solid var(--danger)",
          borderRadius: "var(--r)",
          padding: "12px 16px",
        }}
      >
        {(personQ.error as Error).message}
      </div>
    );
  if (!personQ.data) return <p>未找到</p>;
  return <PersonEntityBody data={personQ.data} disambiguate={disambiguate} />;
}

function PersonEntityBody({
  data,
  disambiguate,
}: {
  data: PersonDetail;
  disambiguate: DisambiguateResponse | null;
}): JSX.Element {
  const totalOption = useMemo(() => {
    const sorted = [...data.total_value_series].sort((a, b) => a.date.localeCompare(b.date));
    return {
      tooltip: {
        trigger: "axis",
        backgroundColor: "var(--bg-elev)",
        borderColor: "var(--line)",
        textStyle: { color: "var(--fg)", fontSize: 12 },
      },
      grid: { left: 70, right: 20, top: 20, bottom: 40 },
      xAxis: {
        type: "category",
        data: sorted.map((p) => formatDate(p.date)),
        axisLabel: { color: "var(--muted)", fontSize: 11 },
        axisLine: { lineStyle: { color: "var(--chart-grid)" } },
      },
      yAxis: {
        type: "value",
        name: "总市值 (元)",
        nameTextStyle: { color: "var(--muted)" },
        splitLine: { lineStyle: { color: "var(--chart-grid)" } },
        axisLabel: { color: "var(--muted)", fontSize: 11 },
      },
      series: [
        {
          name: "总市值",
          type: "line",
          smooth: true,
          symbol: "circle",
          symbolSize: 6,
          itemStyle: { color: "var(--accent)" },
          areaStyle: { opacity: 0.15, color: "var(--accent)" },
          data: sorted.map((p) => p.value),
        },
      ],
    };
  }, [data]);

  const companyCols = useMemo<ColumnDef<CompanyHolding, unknown>[]>(
    () => [
      {
        header: "公司",
        accessorKey: "stock_name",
        cell: (info) => (
          <a href={`#/c/${info.row.original.stock_code}`}>{info.row.original.stock_name}</a>
        ),
      },
      {
        header: "代码",
        accessorKey: "stock_code",
        size: 100,
        cell: (info) => (
          <code style={{ fontSize: 11, background: "none", border: "none", padding: 0 }}>
            {info.row.original.stock_code}
          </code>
        ),
      },
      {
        header: "最新报告期",
        accessorKey: "report_date",
        cell: (info) => (
          <span className="tabular muted" style={{ fontSize: 12 }}>
            {formatDate(info.row.original.report_date)}
          </span>
        ),
      },
      {
        header: "名次",
        accessorKey: "rank",
        size: 60,
        cell: (info) => <span className="tabular">{info.row.original.rank || "—"}</span>,
      },
      {
        header: "持股",
        accessorKey: "holdings",
        cell: (info) => <span className="tabular">{formatShares(info.row.original.holdings)}</span>,
      },
      {
        header: "占比",
        accessorKey: "pct_total",
        cell: (info) => <span className="tabular">{formatPct(info.row.original.pct_total)}</span>,
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
    ],
    [],
  );

  const coCols = useMemo<ColumnDef<CoholderSummary, unknown>[]>(
    () => [
      {
        header: "协同股东",
        accessorKey: "name",
        cell: (info) =>
          info.row.original.is_person ? (
            <a href={`#/p/${encodeURIComponent(info.row.original.name)}`}>
              {info.row.original.name}
            </a>
          ) : (
            info.row.original.name
          ),
      },
      {
        header: "共同公司数",
        accessorKey: "co_count",
        cell: (info) => (
          <span className="tabular" style={{ fontWeight: 600 }}>
            {info.row.original.co_count}
          </span>
        ),
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
    ],
    [],
  );

  const latestMV = totalRecent(data);
  const wd = data.wikidata;

  return (
    <div>
      <header
        style={{
          marginBottom: 24,
          padding: "var(--s-5)",
          background: "var(--bg-elev)",
          border: "1px solid var(--line)",
          borderRadius: "var(--r-lg)",
          position: "relative",
          overflow: "hidden",
        }}
      >
        <div
          aria-hidden
          style={{ position: "absolute", inset: 0, background: "var(--focus-grad)" }}
        />
        <div
          style={{
            position: "relative",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "flex-start",
            gap: 16,
            flexWrap: "wrap",
          }}
        >
          <div>
            <h1>
              {data.name}
              {data.bucket_meta && (
                <span className="muted" style={{ fontSize: 16, fontWeight: 400, marginLeft: 8 }}>
                  #{data.bucket_meta.bucket_idx} / {data.bucket_meta.total_buckets}
                </span>
              )}
            </h1>
            {data.bucket_meta && (
              <div style={{ marginTop: 8 }}>
                <ConfidenceBadge
                  level={data.bucket_meta.level}
                  label={data.bucket_meta.label}
                  evidence={data.bucket_meta.evidence}
                />
              </div>
            )}
            {disambiguate && disambiguate.multi_company_buckets > 1 && (
              <p style={{ marginTop: 10 }}>
                <a href={`#/p/${encodeURIComponent(data.name)}`} style={{ fontSize: 12 }}>
                  ← 回到 Hub（共 {disambiguate.total_buckets} 个候选实体）
                </a>
              </p>
            )}
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <KPI label="持仓公司" value={`${data.companies.length} 家`} />
            <KPI label="总市值" value={formatYuan(latestMV)} accent />
          </div>
        </div>
      </header>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "minmax(0, 2fr) minmax(280px, 1fr)",
          gap: 16,
        }}
      >
        <section className="card" style={{ padding: 20 }}>
          <h2 style={{ marginBottom: 12 }}>持仓公司</h2>
          <DataTable
            data={data.companies}
            columns={companyCols}
            urlKey="ct"
            defaultSort={[{ id: "holdings_value", desc: true }]}
            pageSize={15}
          />
        </section>
        <aside style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {wd?.qid && (
            <div className="card" style={{ padding: 16 }}>
              <header style={{ marginBottom: 8 }}>
                <h3 style={{ fontSize: 13 }}>
                  Wikidata <code style={{ fontSize: 11 }}>{wd.qid}</code>
                </h3>
              </header>
              {wd.label && <p style={{ fontSize: 13, marginBottom: 4 }}>{wd.label}</p>}
              {wd.description && (
                <p className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
                  {wd.description}
                </p>
              )}
              <dl style={{ margin: 0, fontSize: 12, lineHeight: 1.8 }}>
                {wd.birth && <DRow k="出生" v={wd.birth} />}
                {wd.occupations && <DRow k="职业" v={wd.occupations} />}
                {wd.employer && <DRow k="雇主" v={wd.employer} />}
              </dl>
              {wd.zh_wiki && (
                <a
                  href={wd.zh_wiki}
                  target="_blank"
                  rel="noreferrer"
                  style={{ fontSize: 12, marginTop: 8, display: "inline-block" }}
                >
                  中文维基 ↗
                </a>
              )}
              <p className="faint" style={{ fontSize: 11, marginTop: 10 }}>
                关联可能指向其他同名实体，需人工核对。
              </p>
            </div>
          )}
          <a
            href={`#/n/${encodeURIComponent(data.name)}`}
            className="card card-hover"
            style={{ padding: 16, display: "block", color: "var(--fg)", textDecoration: "none" }}
          >
            <div style={{ fontWeight: 600, fontSize: 14 }}>查看 Ego-Network →</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 2 }}>
              焦点出发的一/二跳关系图
            </div>
          </a>
        </aside>
      </div>

      {data.total_value_series.length > 1 && (
        <section className="card" style={{ padding: 20, marginTop: 24 }}>
          <h2 style={{ marginBottom: 12 }}>总市值时序</h2>
          <EChartsWrapper option={totalOption} height={260} />
        </section>
      )}

      <section className="card" style={{ padding: 20, marginTop: 24 }}>
        <h2 style={{ marginBottom: 12 }}>常见协同股东</h2>
        <DataTable
          data={data.coholders}
          columns={coCols}
          urlKey="cp"
          defaultSort={[{ id: "co_count", desc: true }]}
          pageSize={20}
        />
      </section>
    </div>
  );
}

function DRow({ k, v }: { k: string; v: string }): JSX.Element {
  return (
    <div style={{ display: "flex", gap: 8 }}>
      <dt className="faint" style={{ minWidth: 36 }}>
        {k}
      </dt>
      <dd style={{ margin: 0 }}>{v}</dd>
    </div>
  );
}

function KPI({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}): JSX.Element {
  return (
    <div
      style={{
        background: accent ? "var(--accent-bg)" : "var(--bg)",
        border: `1px solid ${accent ? "var(--accent)" : "var(--line)"}`,
        borderRadius: "var(--r)",
        padding: "10px 16px",
        minWidth: 110,
      }}
    >
      <div
        className="faint"
        style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.06em" }}
      >
        {label}
      </div>
      <div
        className="tabular"
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: accent ? "var(--accent-fg)" : "var(--fg-strong)",
          marginTop: 2,
        }}
      >
        {value}
      </div>
    </div>
  );
}

function totalRecent(data: PersonDetail): number | null {
  const s = data.total_value_series;
  if (s.length === 0) return null;
  const last = s[s.length - 1];
  return last ? last.value : null;
}
