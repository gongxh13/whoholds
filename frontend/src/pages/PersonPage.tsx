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
      {disambiguateQ.isLoading && <p style={{ color: "var(--muted)" }}>加载中…</p>}
      {disambiguateQ.error && <PersonEntity name={name} bucket={bucket} disambiguate={null} />}
      {disambiguateQ.data && <Route data={disambiguateQ.data} name={name} bucket={bucket} />}
    </AppShell>
  );
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
      <h1 style={{ marginTop: 0 }}>{data.name}</h1>
      <p style={{ color: "var(--muted)" }}>
        在 <b>{data.total_companies}</b> 家公司被披露为前十大股东 — 拓扑分析推断为{" "}
        <b>{data.total_buckets}</b> 个候选实体（{data.multi_company_buckets} 个多公司桶 +{" "}
        {data.singletons} 个单飞）。下面每张卡片是一个候选实体。
      </p>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(360px, 1fr))",
          gap: 16,
          marginTop: 20,
        }}
      >
        {data.buckets.map((b) => (
          <a
            key={b.bucket_idx}
            href={`#/p/${encodeURIComponent(data.name)}/${b.bucket_idx}`}
            style={cardLink}
          >
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
              <strong>
                {data.name} <span style={{ color: "var(--muted)" }}>#{b.bucket_idx}</span>
              </strong>
              <ConfidenceBadge level={b.level} label={b.label} />
            </div>
            <div style={{ color: "var(--muted)", fontSize: 13 }}>{b.evidence}</div>
            <div style={{ fontSize: 13, marginTop: 8 }}>
              <span>{b.size} 家公司</span>
              {b.top_peers.length > 0 && (
                <span style={{ color: "var(--muted)", marginLeft: 8 }}>
                  常见协同: {b.top_peers.slice(0, 3).join(" / ")}
                </span>
              )}
            </div>
          </a>
        ))}
      </div>
      {data.singletons > 0 && (
        <section style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>
            单飞桶预览（前 30）— 这些公司里 {data.name} 没和其他个人股东协同
          </h2>
          <ul style={{ columns: 3, gap: 16 }}>
            {data.singletons_preview.map((s) => (
              <li key={s.stock_code}>
                <a href={`#/c/${s.stock_code}`}>{s.stock_name}</a>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
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

  if (personQ.isLoading) return <p style={{ color: "var(--muted)" }}>加载中…</p>;
  if (personQ.error) return <p style={{ color: "#c0392b" }}>{(personQ.error as Error).message}</p>;
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
      tooltip: { trigger: "axis" },
      grid: { left: 60, right: 20, top: 20, bottom: 30 },
      xAxis: { type: "category", data: sorted.map((p) => formatDate(p.date)) },
      yAxis: { type: "value", name: "总市值 (元)" },
      series: [
        {
          name: "总市值",
          type: "line",
          smooth: true,
          symbol: "circle",
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
      { header: "代码", accessorKey: "stock_code" },
      {
        header: "最新报告期",
        accessorKey: "report_date",
        cell: (info) => formatDate(info.row.original.report_date),
      },
      { header: "名次", accessorKey: "rank" },
      {
        header: "持股",
        accessorKey: "holdings",
        cell: (info) => formatShares(info.row.original.holdings),
      },
      {
        header: "占比",
        accessorKey: "pct_total",
        cell: (info) => formatPct(info.row.original.pct_total),
      },
      {
        header: "市值",
        accessorKey: "holdings_value",
        cell: (info) => formatYuan(info.row.original.holdings_value ?? null),
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
      { header: "共同公司数", accessorKey: "co_count" },
      {
        header: "类型",
        cell: (info) => (info.row.original.is_person ? "个人" : "机构"),
      },
    ],
    [],
  );

  const latestMV = totalRecent(data);
  const wd = data.wikidata;

  return (
    <div>
      <header style={{ marginBottom: 16 }}>
        <h1 style={{ marginTop: 0, marginBottom: 4 }}>
          {data.name}
          {data.bucket_meta && (
            <span style={{ color: "var(--muted)", fontSize: 16, marginLeft: 8 }}>
              #{data.bucket_meta.bucket_idx} / {data.bucket_meta.total_buckets}
            </span>
          )}
        </h1>
        {data.bucket_meta && (
          <ConfidenceBadge
            level={data.bucket_meta.level}
            label={data.bucket_meta.label}
            evidence={data.bucket_meta.evidence}
          />
        )}
        {disambiguate && disambiguate.multi_company_buckets > 1 && (
          <p style={{ marginTop: 8 }}>
            <a href={`#/p/${encodeURIComponent(data.name)}`}>
              ← 回到 Hub（共 {disambiguate.total_buckets} 个候选实体）
            </a>
          </p>
        )}
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 24 }}>
        <section>
          <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>
            持仓公司 · {data.companies.length} 家 · 总市值 {formatYuan(latestMV)}
          </h2>
          <DataTable
            data={data.companies}
            columns={companyCols}
            urlKey="ct"
            defaultSort={[{ id: "holdings_value", desc: true }]}
            pageSize={15}
          />
        </section>
        <section>
          {wd?.qid && (
            <div style={card}>
              <h3 style={{ marginTop: 0, fontSize: "1rem" }}>
                Wikidata · <code style={code}>{wd.qid}</code>
              </h3>
              {wd.label && <p style={{ margin: "4px 0" }}>{wd.label}</p>}
              {wd.description && (
                <p style={{ margin: "4px 0", color: "var(--muted)", fontSize: 13 }}>
                  {wd.description}
                </p>
              )}
              {wd.birth && <p style={{ margin: "4px 0" }}>出生 · {wd.birth}</p>}
              {wd.occupations && <p style={{ margin: "4px 0" }}>职业 · {wd.occupations}</p>}
              {wd.employer && <p style={{ margin: "4px 0" }}>雇主 · {wd.employer}</p>}
              {wd.zh_wiki && (
                <p style={{ margin: "4px 0" }}>
                  <a href={wd.zh_wiki} target="_blank" rel="noreferrer">
                    中文维基 ↗
                  </a>
                </p>
              )}
              <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
                注：Wikidata 关联可能指向其他同名实体，需人工核对。
              </p>
            </div>
          )}
          <div style={{ marginTop: 16 }}>
            <a href={`#/n/${encodeURIComponent(data.name)}`} style={cardLink}>
              <strong>查看 Ego-Network →</strong>
              <div style={{ color: "var(--muted)", fontSize: 13 }}>
                焦点出发的一/二跳网络（节点上限 100）
              </div>
            </a>
          </div>
        </section>
      </div>

      {data.total_value_series.length > 1 && (
        <section style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>总市值时序</h2>
          <EChartsWrapper option={totalOption} height={260} />
        </section>
      )}

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>
          常见协同股东（前 {data.coholders.length}）
        </h2>
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

function totalRecent(data: PersonDetail): number | null {
  const s = data.total_value_series;
  if (s.length === 0) return null;
  const last = s[s.length - 1];
  return last ? last.value : null;
}

const card: React.CSSProperties = {
  background: "var(--bg-elev)",
  border: "1px solid var(--line)",
  borderRadius: 8,
  padding: 16,
};
const cardLink: React.CSSProperties = {
  ...card,
  display: "block",
  color: "var(--fg)",
  textDecoration: "none",
};
const code: React.CSSProperties = {
  background: "rgba(127,127,127,.16)",
  padding: "0 4px",
  borderRadius: 3,
  fontSize: "0.85em",
};
