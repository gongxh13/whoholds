import { AppShell } from "@/components/AppShell";
import { EChartsWrapper } from "@/components/EChartsWrapper";
import { type NetworkResponse, getNetwork } from "@/lib/api";
import type { RouteParams } from "@/lib/router";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";

const COLORS = {
  focus: "#f78166",
  person: "#4493f8",
  inst: "#8b949e",
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
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 24,
          gap: 16,
          flexWrap: "wrap",
        }}
      >
        <div>
          <h1>Ego-Network</h1>
          <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
            焦点 <a href={`#/p/${encodeURIComponent(focus)}`}>{focus}</a> — 节点上限 100（design.md
            §三铁律）
          </p>
        </div>
        <div
          className="card"
          style={{ padding: 14, display: "flex", gap: 16, alignItems: "center" }}
        >
          <Control
            id="hops"
            label="跳数"
            element={
              <select
                id="hops"
                value={hops}
                onChange={(e) => setHops(Number(e.target.value))}
                className="input"
              >
                <option value={1}>1 跳</option>
                <option value={2}>2 跳</option>
              </select>
            }
          />
          <Control
            id="min-pct"
            label="最小占股 %"
            element={
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <input
                  id="min-pct"
                  type="range"
                  min={0}
                  max={5}
                  step={0.1}
                  value={minPct}
                  onChange={(e) => setMinPct(Number(e.target.value))}
                  style={{ width: 100 }}
                />
                <span className="tabular" style={{ fontSize: 12, minWidth: 36 }}>
                  {minPct.toFixed(1)}%
                </span>
              </div>
            }
          />
        </div>
      </header>

      {isLoading && <p className="muted">加载中…</p>}
      {error && (
        <div
          style={{
            background: "var(--danger-bg)",
            color: "var(--danger)",
            border: "1px solid var(--danger)",
            padding: "10px 14px",
            borderRadius: "var(--r)",
          }}
        >
          {(error as Error).message}
        </div>
      )}
      {data && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          {data.stats.truncated && (
            <div
              style={{
                background: "var(--warn-bg)",
                color: "var(--warn)",
                padding: "8px 16px",
                fontSize: 12,
                borderBottom: "1px solid var(--warn)",
              }}
            >
              ⚠ 节点已达 100 上限，结果已截断。请收紧筛选条件。
            </div>
          )}
          <EChartsWrapper option={option} height={620} />
          <footer
            style={{
              display: "flex",
              gap: 16,
              padding: "10px 16px",
              borderTop: "1px solid var(--line-muted)",
              background: "var(--bg-sunken)",
              fontSize: 12,
            }}
          >
            <Legend color={COLORS.focus} label="焦点" />
            <Legend color={COLORS.person} label={`个人 ${countKind(data, "person")}`} />
            <Legend color={COLORS.inst} label={`机构 ${countKind(data, "inst")}`} />
            <Legend color={COLORS.company} label={`公司 ${countKind(data, "company")}`} square />
            <span className="faint" style={{ marginLeft: "auto" }}>
              {data.stats.n_nodes} 节点 · {data.edges.length} 边
            </span>
          </footer>
        </div>
      )}
    </AppShell>
  );
}

function Control({
  id,
  label,
  element,
}: {
  id: string;
  label: string;
  element: React.ReactNode;
}): JSX.Element {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <label htmlFor={id} className="muted" style={{ fontSize: 12 }}>
        {label}
      </label>
      {element}
    </div>
  );
}

function Legend({
  color,
  label,
  square,
}: {
  color: string;
  label: string;
  square?: boolean;
}): JSX.Element {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <span
        style={{
          display: "inline-block",
          width: 10,
          height: 10,
          background: color,
          borderRadius: square ? 2 : "50%",
        }}
      />
      <span className="muted">{label}</span>
    </span>
  );
}

function countKind(d: NetworkResponse, kind: string): number {
  return d.nodes.filter((n) => n.kind === kind).length;
}

function buildOption(d: NetworkResponse, focus: string) {
  return {
    tooltip: {
      backgroundColor: "var(--bg-elev)",
      borderColor: "var(--line)",
      textStyle: { color: "var(--fg)", fontSize: 12 },
    },
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        symbolSize: (_v: unknown, p: { data: { _size?: number } }) => p.data._size ?? 22,
        label: {
          show: true,
          position: "right",
          fontSize: 11,
          color: "var(--muted)",
        },
        edgeLength: 110,
        force: { repulsion: 350, gravity: 0.08, edgeLength: 110 },
        emphasis: { focus: "adjacency", label: { color: "var(--fg)" } },
        data: d.nodes.map((n) => ({
          id: n.id,
          name: n.label,
          symbol: n.kind === "company" ? "rect" : "circle",
          itemStyle: {
            color: colorOf(n, focus),
            borderColor: n.id === `p:${focus}` ? "var(--focus-orange)" : "transparent",
            borderWidth: n.id === `p:${focus}` ? 3 : 0,
          },
          _size: n.kind === "company" ? 44 : n.id === `p:${focus}` ? 32 : 20,
        })),
        links: d.edges.map((e) => ({
          source: e.source,
          target: e.target,
          lineStyle: {
            width: e.kind === "focus" ? 2 : 1,
            color: e.kind === "indirect" ? "var(--faint)" : "var(--line)",
            type: e.kind === "indirect" ? "dashed" : "solid",
            opacity: 0.7,
          },
        })),
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
