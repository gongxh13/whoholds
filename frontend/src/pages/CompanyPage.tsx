import type { RouteParams } from "@/lib/router";

export function CompanyPage({ params }: { params: RouteParams }): JSX.Element {
  // TODO(PR 3): wire this to GET /api/company/{code} with TanStack Query.
  return (
    <main>
      <h1>公司 · {params.code}</h1>
      <p style={{ color: "var(--muted)" }}>PR 3 接入：前十大股东表 + 堆叠时序图</p>
      <p>
        <a href="#/">← 返回</a>
      </p>
    </main>
  );
}
