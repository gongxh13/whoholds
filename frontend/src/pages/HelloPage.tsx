import { ApiError, type HealthResponse, apiGet } from "@/lib/api";
import { useEffect, useState } from "react";

type State =
  | { kind: "loading" }
  | { kind: "ok"; data: HealthResponse }
  | { kind: "error"; message: string };

export function HelloPage(): JSX.Element {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    apiGet<HealthResponse>("/api/health")
      .then((data) => setState({ kind: "ok", data }))
      .catch((e: unknown) => {
        const message = e instanceof ApiError ? e.message : "backend unreachable";
        setState({ kind: "error", message });
      });
  }, []);

  return (
    <main>
      <h1>whoholds</h1>
      <p style={{ color: "var(--muted)" }}>A 股股东网络与时间线分析 — 前端脚手架 (PR 2)</p>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: "1.1rem" }}>后端连通性</h2>
        <BackendStatus state={state} />
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ fontSize: "1.1rem" }}>路由占位</h2>
        <ul>
          <li>
            <a href="#/discover">#/discover</a> — 发现页
          </li>
          <li>
            <a href="#/c/sh600519">#/c/sh600519</a> — 公司视角（贵州茅台）
          </li>
          <li>
            <a href="#/p/%E5%90%95%E5%BC%BA">#/p/吕强</a> — 个人 Hub
          </li>
          <li>
            <a href="#/n/%E7%8E%8B%E4%BC%A0%E7%A6%8F">#/n/王传福</a> — Ego-Network
          </li>
        </ul>
      </section>
    </main>
  );
}

function BackendStatus({ state }: { state: State }): JSX.Element {
  if (state.kind === "loading") return <p>检测中…</p>;
  if (state.kind === "error") {
    return (
      <p style={{ color: "#c0392b" }}>
        ✗ {state.message}（启动后端：<code>cd backend && uv run uvicorn app.main:app --reload</code>
        ）
      </p>
    );
  }
  const dbs = Object.entries(state.data.databases);
  return (
    <div>
      <p>✓ /api/health = {state.data.status}</p>
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
