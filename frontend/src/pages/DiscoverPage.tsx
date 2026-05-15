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

  return (
    <AppShell>
      <Hero nCross={crossQ.data?.length ?? null} nPairs={pairsQ.data?.length ?? null} />

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr",
          gap: 24,
          marginTop: 24,
        }}
      >
        <Panel
          title="跨持股个人股东榜"
          subtitle="出现在最多家上市公司前十大股东的自然人 — 同名问题已用 Layer-2 拓扑算法预先拆桶。"
        >
          <CrossHoldersTable q={crossQ} />
        </Panel>

        <Panel
          title="协同股东对榜"
          subtitle="两个个人在 N 家公司同时位列前十大 — 强联结信号常对应家族 / 一致行动人 / 投资团伙。"
        >
          <CoholderPairsTable q={pairsQ} />
        </Panel>
      </div>
    </AppShell>
  );
}

function Hero({
  nCross,
  nPairs,
}: {
  nCross: number | null;
  nPairs: number | null;
}): JSX.Element {
  return (
    <section
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-lg)",
        padding: "var(--s-6) var(--s-5)",
        position: "relative",
        overflow: "hidden",
      }}
    >
      <div
        aria-hidden
        style={{
          position: "absolute",
          inset: 0,
          background: "var(--focus-grad)",
          pointerEvents: "none",
        }}
      />
      <div
        style={{
          position: "relative",
          display: "flex",
          gap: 32,
          alignItems: "flex-end",
          flexWrap: "wrap",
        }}
      >
        <div style={{ flex: "1 1 360px", minWidth: 280 }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "3px 10px",
              borderRadius: "var(--r-pill)",
              background: "var(--accent-bg)",
              color: "var(--accent-fg)",
              fontSize: 11,
              fontWeight: 600,
              marginBottom: 12,
            }}
          >
            <span>●</span> 全市场预聚合
          </div>
          <h1 style={{ fontSize: 28, marginBottom: 8 }}>发现 · A 股股东网络</h1>
          <p style={{ color: "var(--muted)", maxWidth: 640, fontSize: 14 }}>
            从前十大股东披露数据出发 — 谁在跨多家公司持股、谁和谁是常见合伙人、谁可能是家族关系。
            点击行进入个人 / 公司 / Ego-Network 三种视图。
          </p>
        </div>
        <div style={{ display: "flex", gap: 16 }}>
          <Stat label="个人股东榜" value={nCross} />
          <Stat label="协同对榜" value={nPairs} />
        </div>
      </div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: number | null }): JSX.Element {
  return (
    <div
      style={{
        background: "var(--bg)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r)",
        padding: "12px 18px",
        minWidth: 110,
      }}
    >
      <div
        style={{
          fontSize: 11,
          color: "var(--faint)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
        }}
      >
        {label}
      </div>
      <div
        style={{
          fontSize: 22,
          fontWeight: 700,
          color: "var(--fg-strong)",
          fontVariantNumeric: "tabular-nums",
          marginTop: 2,
        }}
      >
        {value == null ? "—" : value}
      </div>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <section
      style={{
        background: "var(--bg-elev)",
        border: "1px solid var(--line)",
        borderRadius: "var(--r-lg)",
        padding: "var(--s-5)",
      }}
    >
      <header style={{ marginBottom: 16 }}>
        <h3 style={{ fontSize: 16, marginBottom: 4 }}>{title}</h3>
        {subtitle && <p style={{ color: "var(--muted)", fontSize: 13 }}>{subtitle}</p>}
      </header>
      {children}
    </section>
  );
}

function CrossHoldersTable({
  q,
}: {
  q: ReturnType<typeof useQuery<CrossHolder[]>>;
}): JSX.Element {
  const columns = useMemo<ColumnDef<CrossHolder, unknown>[]>(
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
        cell: (info) => (
          <span className="tabular" style={{ fontWeight: 600 }}>
            {info.row.original.n_companies}
          </span>
        ),
      },
      {
        header: "总市值",
        accessorKey: "total_value",
        cell: (info) => (
          <span className="tabular muted">{formatYuan(info.row.original.total_value ?? null)}</span>
        ),
      },
      {
        header: "示例公司",
        cell: (info) => (
          <span className="muted" style={{ fontSize: 12 }}>
            {info.row.original.companies
              .slice(0, 4)
              .map((c) => c.stock_name)
              .join("、")}
            {info.row.original.companies.length > 4 ? " …" : ""}
          </span>
        ),
      },
    ],
    [],
  );
  return <QueryTable q={q} columns={columns} urlKey="cx" sortDesc="n_companies" />;
}

function CoholderPairsTable({
  q,
}: {
  q: ReturnType<typeof useQuery<CoholderPair[]>>;
}): JSX.Element {
  const columns = useMemo<ColumnDef<CoholderPair, unknown>[]>(
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
        header: "示例",
        cell: (info) => {
          const segs = info.row.original.company_list
            .split(",")
            .slice(0, 4)
            .map((s) => s.split("|")[1] ?? s);
          return (
            <span className="muted" style={{ fontSize: 12 }}>
              {segs.join("、")}
              {info.row.original.company_list.split(",").length > 4 ? " …" : ""}
            </span>
          );
        },
      },
    ],
    [],
  );
  return <QueryTable q={q} columns={columns} urlKey="cp" sortDesc="co_count" />;
}

function QueryTable<T extends object>({
  q,
  columns,
  urlKey,
  sortDesc,
}: {
  q: { isLoading: boolean; error: unknown; data: T[] | undefined };
  columns: ColumnDef<T, unknown>[];
  urlKey: string;
  sortDesc: string;
}): JSX.Element {
  if (q.isLoading) return <SkeletonTable />;
  if (q.error) return <ErrorBox message={(q.error as Error).message} />;
  if (!q.data || q.data.length === 0) return <EmptyState />;
  return (
    <DataTable
      data={q.data}
      columns={columns}
      urlKey={urlKey}
      defaultSort={[{ id: sortDesc, desc: true }]}
      pageSize={20}
    />
  );
}

function SkeletonTable(): JSX.Element {
  return (
    <div>
      {Array.from({ length: 6 }, (_, i) => `skel-${i}`).map((id, i) => (
        <div
          key={id}
          style={{
            height: 36,
            background: "var(--bg-sunken)",
            borderRadius: "var(--r-sm)",
            marginBottom: 6,
            opacity: 0.4 + (6 - i) / 12,
          }}
        />
      ))}
    </div>
  );
}

function ErrorBox({ message }: { message: string }): JSX.Element {
  return (
    <div
      style={{
        background: "var(--danger-bg)",
        color: "var(--danger)",
        border: "1px solid var(--danger)",
        padding: "10px 14px",
        borderRadius: "var(--r)",
        fontSize: 13,
      }}
    >
      {message}
    </div>
  );
}

function EmptyState(): JSX.Element {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "var(--s-6) var(--s-4)",
        color: "var(--muted)",
        background: "var(--bg-sunken)",
        borderRadius: "var(--r)",
        border: "1px dashed var(--line)",
      }}
    >
      <div style={{ fontSize: 28, marginBottom: 8 }}>∅</div>
      <div style={{ fontSize: 13 }}>暂无数据 — 请先跑 bootstrap 抓数据</div>
      <code style={{ fontSize: 12, marginTop: 10, display: "inline-block" }}>
        python run.py bootstrap
      </code>
    </div>
  );
}
