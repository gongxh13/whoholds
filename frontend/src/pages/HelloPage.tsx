import { AppShell } from "@/components/AppShell";
import { type HealthResponse, getHealth } from "@/lib/api";
import { useQuery } from "@tanstack/react-query";

export function HelloPage(): JSX.Element {
  const { data, isLoading, error } = useQuery({
    queryKey: ["health"],
    queryFn: () => getHealth(),
    retry: 0,
  });

  return (
    <AppShell>
      <h1 style={{ marginTop: 0 }}>whoholds</h1>
      <p style={{ color: "var(--muted)" }}>A 股股东网络与时间线分析</p>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: "1rem" }}>后端连通性</h2>
        <BackendStatus data={data} isLoading={isLoading} error={error as Error | null} />
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: "1rem" }}>视图入口</h2>
        <ul>
          <li>
            <a href="#/discover">#/discover</a> — 发现页（跨持股榜 + 协同对榜）
          </li>
          <li>
            <a href="#/c/sh600519">#/c/sh600519</a> — 公司视角（贵州茅台示例）
          </li>
          <li>
            <a href="#/p/%E5%90%95%E5%BC%BA">#/p/吕强</a> — 个人 Hub（多桶分发）
          </li>
          <li>
            <a href="#/n/%E7%8E%8B%E4%BC%A0%E7%A6%8F">#/n/王传福</a> — Ego-Network
          </li>
        </ul>
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
  if (isLoading) return <p>检测中…</p>;
  if (error)
    return (
      <p style={{ color: "#c0392b" }}>
        ✗ {error.message}（启动后端：<code>cd backend && uv run uvicorn app.main:app --reload</code>
        ）
      </p>
    );
  if (!data) return <p>—</p>;
  const dbs = Object.entries(data.databases);
  return (
    <div>
      <p>✓ /api/health = {data.status}</p>
      <ul style={{ marginTop: 4 }}>
        {dbs.map(([name, exists]) => (
          <li key={name}>
            {exists ? "✓" : "✗"} {name}.db {exists ? "" : "(尚未迁移)"}
          </li>
        ))}
      </ul>
    </div>
  );
}
