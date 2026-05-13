import type { RouteParams } from "@/lib/router";

export function NetworkPage({ params }: { params: RouteParams }): JSX.Element {
  // TODO(PR 5): port Ego-Network from prototype (ECharts force graph, 100-node cap).
  return (
    <main>
      <h1>Ego-Network · {params.name}</h1>
      <p style={{ color: "var(--muted)" }}>PR 5 接入：ECharts force graph（节点 ≤ 100 铁律）</p>
      <p>
        <a href="#/">← 返回</a>
      </p>
    </main>
  );
}
