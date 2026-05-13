import type { RouteParams } from "@/lib/router";

export function PersonPage({ params }: { params: RouteParams }): JSX.Element {
  // TODO(PR 5): person hub (when bucket undefined) vs entity (with bucket).
  const bucket = params.bucket;
  return (
    <main>
      <h1>
        {params.name}
        {bucket ? <span style={{ color: "var(--muted)" }}> · 桶 #{bucket}</span> : null}
      </h1>
      <p style={{ color: "var(--muted)" }}>
        {bucket
          ? "PR 5 接入：实体页（含 Wikidata / 时序 / 协同）"
          : "PR 5 接入：Hub 页（多桶分发）"}
      </p>
      <p>
        <a href="#/">← 返回</a>
      </p>
    </main>
  );
}
