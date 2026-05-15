import { AppShell } from "@/components/AppShell";
import { type HealthResponse, getHealth } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

export function HelloPage(): JSX.Element {
  const { data, isLoading, error } = useQuery({
    queryKey: ["health"],
    queryFn: () => getHealth(),
    retry: 0,
    refetchInterval: 5_000,
  });

  return (
    <AppShell>
      <h1>系统状态</h1>
      <p className="muted" style={{ marginTop: 6 }}>
        每 5 秒自动检测后端连通性 + 5 个 SQLite 文件是否就绪。
      </p>

      <section style={{ marginTop: 28 }}>
        <BackendStatus data={data} isLoading={isLoading} error={error as Error | null} />
      </section>

      <section style={{ marginTop: 28 }}>
        <h2 style={{ marginBottom: 12 }}>视图入口</h2>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 12,
          }}
        >
          <LinkCard href="#/discover" title="发现" desc="跨持股 + 协同对榜" />
          <LinkCard href="#/c/sz000333" title="公司视角" desc="美的集团示例" />
          <LinkCard href="#/p/王传福" title="个人视角" desc="比亚迪董事长示例" />
          <LinkCard href="#/n/王传福" title="Ego-Network" desc="一/二跳关系图" />
          <LinkCard href="#/annotations" title="标注" desc="合并 / 拆分 / 绑 QID" />
        </div>
      </section>
    </AppShell>
  );
}

function BackendStatus({
  data,
  isLoading,
  error,
}: {
  data: HealthResponse | undefined;
  isLoading: boolean;
  error: Error | null;
}): JSX.Element {
  if (isLoading) {
    return <Box tone="muted">检测中…</Box>;
  }
  if (error) {
    return (
      <Box tone="danger" title="后端不可达">
        {error.message}
        <div style={{ marginTop: 8, fontSize: 12 }}>
          启动后端：<code>cd backend && uv run uvicorn app.main:app --reload</code>
        </div>
      </Box>
    );
  }
  if (!data) return <Box tone="muted">—</Box>;
  const dbs = Object.entries(data.databases);
  const allGreen = dbs.every(([, ok]) => ok);

  return (
    <Box tone={allGreen ? "success" : "warn"} title={`/api/health = ${data.status}`}>
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
          gap: 8,
          marginTop: 10,
        }}
      >
        {dbs.map(([name, exists]) => (
          <div
            key={name}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "6px 10px",
              border: "1px solid var(--line)",
              borderRadius: "var(--r-sm)",
              background: "var(--bg-elev)",
            }}
          >
            <Dot ok={exists} />
            <code style={{ flex: 1, background: "none", border: "none", padding: 0 }}>
              {name}.db
            </code>
            <span className="faint" style={{ fontSize: 11 }}>
              {exists ? "ok" : "missing"}
            </span>
          </div>
        ))}
      </div>
    </Box>
  );
}

function Box({
  tone,
  title,
  children,
}: {
  tone: "success" | "warn" | "danger" | "muted";
  title?: string;
  children: React.ReactNode;
}): JSX.Element {
  const map = {
    success: { bg: "var(--success-bg)", fg: "var(--success)", icon: "✓" },
    warn: { bg: "var(--warn-bg)", fg: "var(--warn)", icon: "!" },
    danger: { bg: "var(--danger-bg)", fg: "var(--danger)", icon: "✗" },
    muted: { bg: "var(--bg-sunken)", fg: "var(--muted)", icon: "…" },
  } as const;
  const s = map[tone];
  return (
    <div
      style={{
        background: s.bg,
        border: `1px solid ${s.fg}`,
        borderRadius: "var(--r)",
        padding: "12px 16px",
        color: s.fg,
        fontSize: 13,
      }}
    >
      {title && (
        <div style={{ fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}>
          <span>{s.icon}</span>
          {title}
        </div>
      )}
      <div style={{ color: "var(--fg)" }}>{children}</div>
    </div>
  );
}

function Dot({ ok }: { ok: boolean }): JSX.Element {
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: ok ? "var(--success)" : "var(--danger)",
        boxShadow: ok ? "0 0 0 3px var(--success-bg)" : "0 0 0 3px var(--danger-bg)",
      }}
    />
  );
}

function LinkCard({
  href,
  title,
  desc,
}: {
  href: string;
  title: string;
  desc: string;
}): JSX.Element {
  return (
    <a
      href={href}
      className="card card-hover"
      style={{
        padding: "14px 16px",
        textDecoration: "none",
        color: "var(--fg)",
        display: "block",
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{title}</div>
      <div className="muted" style={{ fontSize: 12 }}>
        {desc}
      </div>
    </a>
  );
}
