import { AppShell } from "@/components/AppShell";
import { EChartsWrapper } from "@/components/EChartsWrapper";
import { type NetworkResponse, getNetwork } from "@/lib/api";
import type { RouteParams } from "@/lib/router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const COLORS = {
  focus: "#f78166",
  person: "#4493f8",
  inst: "#6e7681",
  company: "#f0883e",
};

export function NetworkPage({ params }: { params: RouteParams }): JSX.Element {
  const focus = params.name ?? "";
  const [hops, setHops] = useState(1);
  const [minPct, setMinPct] = useState(0);

  const { data, isLoading, error } = useQuery({
    queryKey: ["network", focus, hops, minPct],
    queryFn: () => getNetwork(focus, hops, minPct),
  });

  const option = useMemo(() => (data ? buildOption(data, focus) : {}), [data, focus]);

  return (
    <AppShell>
      <h1 style={{ marginTop: 0 }}>
        Ego-Network · <span style={{ color: "var(--muted)" }}>{focus}</span>
      </h1>
      <p style={{ color: "var(--muted)", fontSize: 13 }}>
        节点上限 100 — 触顶时停止扩张（design.md §三铁律）。
      </p>
      <div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 12 }}>
        <label htmlFor="hops" style={lbl}>
          跳数
        </label>
        <select
          id="hops"
          value={hops}
          onChange={(e) => setHops(Number(e.target.value))}
          style={sel}
        >
          <option value={1}>1 跳</option>
          <option value={2}>2 跳</option>
        </select>
        <label htmlFor="min-pct" style={lbl}>
          最小占股 %
        </label>
        <input
          id="min-pct"
          type="range"
          min={0}
          max={5}
          step={0.1}
          value={minPct}
          onChange={(e) => setMinPct(Number(e.target.value))}
        />
        <span style={{ fontVariantNumeric: "tabular-nums" }}>{minPct.toFixed(1)} %</span>
      </div>

      {isLoading && <p style={{ color: "var(--muted)" }}>加载中…</p>}
      {error && <p style={{ color: "#c0392b" }}>{(error as Error).message}</p>}
      {data && (
        <>
          {data.stats.truncated && (
            <p style={{ color: "#bc4c00" }}>
              ⚠ 节点已达 100 上限，结果已截断。请收紧筛选条件查看完整网络。
            </p>
          )}
          <EChartsWrapper option={option} height={620} />
          <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 8 }}>
            人 {countKind(data, "person")} · 机构 {countKind(data, "inst")} · 公司{" "}
            {countKind(data, "company")} · 边 {data.edges.length}
          </p>
        </>
      )}
    </AppShell>
  );
}

function countKind(d: NetworkResponse, kind: string): number {
  return d.nodes.filter((n) => n.kind === kind).length;
}

function buildOption(d: NetworkResponse, focus: string) {
  return {
    tooltip: {},
    legend: [{ data: ["焦点", "个人", "机构", "公司"], bottom: 0 }],
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        symbolSize: (_v: unknown, p: { data: { _size?: number } }) => p.data._size ?? 22,
        edgeLength: 110,
        force: { repulsion: 350, gravity: 0.1, edgeLength: 110 },
        emphasis: { focus: "adjacency" },
        data: d.nodes.map((n) => ({
          id: n.id,
          name: n.label,
          category: n.id === `p:${focus}` ? "焦点" : labelOf(n.kind),
          itemStyle: { color: colorOf(n, focus) },
          _size: n.kind === "company" ? 40 : n.id === `p:${focus}` ? 30 : 20,
        })),
        links: d.edges.map((e) => ({
          source: e.source,
          target: e.target,
          lineStyle: {
            width: e.kind === "focus" ? 2 : 1,
            color: e.kind === "indirect" ? "#7d8590" : "var(--line)",
            type: e.kind === "indirect" ? "dashed" : "solid",
          },
        })),
        categories: [{ name: "焦点" }, { name: "个人" }, { name: "机构" }, { name: "公司" }],
      },
    ],
  };
}

function colorOf(n: NetworkResponse["nodes"][number], focus: string): string {
  if (n.id === `p:${focus}`) return COLORS.focus;
  if (n.kind === "person") return COLORS.person;
  if (n.kind === "inst") return COLORS.inst;
  return COLORS.company;
}

function labelOf(kind: string): string {
  if (kind === "person") return "个人";
  if (kind === "inst") return "机构";
  return "公司";
}

const lbl: React.CSSProperties = { color: "var(--muted)", fontSize: 13 };
const sel: React.CSSProperties = {
  background: "var(--bg-elev)",
  border: "1px solid var(--line)",
  color: "var(--fg)",
  padding: "4px 8px",
  borderRadius: 6,
};
