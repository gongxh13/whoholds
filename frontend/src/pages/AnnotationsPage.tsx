import { AppShell } from "@/components/AppShell";
import {
  type AnnotationOp,
  type AnnotationResponse,
  getAnnotations,
  postAnnotation,
} from "@/lib/api";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

const OPS: { value: AnnotationOp; label: string; help: string }[] = [
  { value: "merge", label: "合并", help: '{"names": ["吕强", "李红"]}' },
  { value: "split", label: "拆分", help: '{"name": "张秀", "bucket": 3}' },
  { value: "bind_qid", label: "绑定 QID", help: '{"name": "王传福", "qid": "Q716030"}' },
  {
    value: "is_person",
    label: "is_person 修正",
    help: '{"name": "某公司基金", "value": false}',
  },
];

export function AnnotationsPage(): JSX.Element {
  const qc = useQueryClient();
  const list = useQuery({ queryKey: ["annotations"], queryFn: () => getAnnotations(100) });
  const [op, setOp] = useState<AnnotationOp>("merge");
  const [payload, setPayload] = useState("");
  const [user, setUser] = useState("anonymous");
  const [err, setErr] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      postAnnotation({
        op,
        payload: JSON.parse(payload || "{}") as Record<string, unknown>,
        user,
      }),
    onSuccess: () => {
      setPayload("");
      setErr(null);
      qc.invalidateQueries({ queryKey: ["annotations"] });
    },
    onError: (e: unknown) => setErr((e as Error).message),
  });

  const opMeta = OPS.find((o) => o.value === op);

  return (
    <AppShell>
      <h1 style={{ marginTop: 0 }}>用户标注</h1>
      <p style={{ color: "var(--muted)" }}>
        合并 / 拆分 / 绑定 Wikidata QID — 写入 entities.user_annotation 表（带 audit trail）。
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          try {
            JSON.parse(payload || "{}");
          } catch (parseErr) {
            setErr(`JSON 解析失败: ${(parseErr as Error).message}`);
            return;
          }
          create.mutate();
        }}
        style={formStyle}
      >
        <label htmlFor="op" style={lbl}>
          操作
        </label>
        <select
          id="op"
          value={op}
          onChange={(e) => setOp(e.target.value as AnnotationOp)}
          style={ctl}
        >
          {OPS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>

        <label htmlFor="payload" style={lbl}>
          payload (JSON)
        </label>
        <textarea
          id="payload"
          rows={4}
          value={payload}
          onChange={(e) => setPayload(e.target.value)}
          placeholder={opMeta?.help}
          style={{ ...ctl, fontFamily: "monospace" }}
        />

        <label htmlFor="user" style={lbl}>
          用户
        </label>
        <input id="user" value={user} onChange={(e) => setUser(e.target.value)} style={ctl} />

        <div style={{ gridColumn: "1 / -1" }}>
          <button type="submit" disabled={create.isPending} style={btn}>
            {create.isPending ? "提交中…" : "提交"}
          </button>
          {err && <span style={{ color: "#c0392b", marginLeft: 12 }}>{err}</span>}
        </div>
      </form>

      <section style={{ marginTop: 32 }}>
        <h2 style={{ fontSize: "1rem", color: "var(--muted)" }}>历史标注（最近 100 条）</h2>
        {list.isLoading && <p>加载中…</p>}
        {list.data && (
          <ul style={{ paddingLeft: 0, listStyle: "none" }}>
            {list.data.map((a) => (
              <Item key={a.id} a={a} />
            ))}
          </ul>
        )}
      </section>
    </AppShell>
  );
}

function Item({ a }: { a: AnnotationResponse }): JSX.Element {
  return (
    <li
      style={{
        border: "1px solid var(--line)",
        background: "var(--bg-elev)",
        padding: "8px 12px",
        marginBottom: 6,
        borderRadius: 6,
        fontSize: 13,
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <strong>{a.op}</strong>
        <span style={{ color: "var(--muted)" }}>
          #{a.id} · {a.user} · {a.ts.slice(0, 19).replace("T", " ")}
        </span>
      </div>
      <pre style={{ margin: "4px 0 0", fontFamily: "monospace", fontSize: 12 }}>
        {JSON.stringify(a.payload, null, 2)}
      </pre>
    </li>
  );
}

const formStyle: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "100px 1fr",
  gap: 8,
  background: "var(--bg-elev)",
  padding: 16,
  borderRadius: 8,
  border: "1px solid var(--line)",
};
const lbl: React.CSSProperties = { color: "var(--muted)", fontSize: 13, alignSelf: "center" };
const ctl: React.CSSProperties = {
  background: "var(--bg)",
  border: "1px solid var(--line)",
  color: "var(--fg)",
  padding: "6px 8px",
  borderRadius: 6,
  fontSize: 13,
};
const btn: React.CSSProperties = {
  background: "var(--accent)",
  color: "white",
  border: "none",
  padding: "6px 14px",
  borderRadius: 6,
  cursor: "pointer",
};
