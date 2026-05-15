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
      <header style={{ marginBottom: 24 }}>
        <h1>用户标注</h1>
        <p className="muted" style={{ fontSize: 13, marginTop: 4 }}>
          合并 / 拆分 / 绑定 Wikidata QID — 写入 entities.user_annotation（带 audit trail），
          触发涉及姓名的消歧重算。
        </p>
      </header>

      <div
        style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 2fr)", gap: 24 }}
      >
        <section className="card" style={{ padding: 20 }}>
          <h2 style={{ marginBottom: 12 }}>新建标注</h2>
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
            style={{ display: "grid", gridTemplateColumns: "1fr", gap: 12 }}
          >
            <Field label="操作" id="op">
              <select
                id="op"
                value={op}
                onChange={(e) => setOp(e.target.value as AnnotationOp)}
                className="input"
              >
                {OPS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </Field>

            <Field label="payload (JSON)" id="payload">
              <textarea
                id="payload"
                rows={5}
                value={payload}
                onChange={(e) => setPayload(e.target.value)}
                placeholder={opMeta?.help}
                className="input"
                style={{ fontFamily: "var(--font-mono)", resize: "vertical" }}
              />
            </Field>

            <Field label="用户" id="user">
              <input
                id="user"
                value={user}
                onChange={(e) => setUser(e.target.value)}
                className="input"
              />
            </Field>

            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <button type="submit" disabled={create.isPending} className="btn btn-primary">
                {create.isPending ? "提交中…" : "提交"}
              </button>
              {err && <span style={{ color: "var(--danger)", fontSize: 12 }}>{err}</span>}
              {create.isSuccess && !err && (
                <span style={{ color: "var(--success)", fontSize: 12 }}>✓ 已提交</span>
              )}
            </div>
          </form>
        </section>

        <section>
          <h2 style={{ marginBottom: 12 }}>历史标注</h2>
          {list.isLoading && <p className="muted">加载中…</p>}
          {list.data && list.data.length === 0 && (
            <div
              className="card"
              style={{
                padding: "var(--s-6)",
                textAlign: "center",
                color: "var(--muted)",
                border: "1px dashed var(--line)",
              }}
            >
              <div style={{ fontSize: 28, marginBottom: 8 }}>∅</div>
              <div style={{ fontSize: 13 }}>暂无标注</div>
            </div>
          )}
          {list.data && list.data.length > 0 && (
            <ul style={{ padding: 0, listStyle: "none", margin: 0, display: "grid", gap: 8 }}>
              {list.data.map((a) => (
                <Item key={a.id} a={a} />
              ))}
            </ul>
          )}
        </section>
      </div>
    </AppShell>
  );
}

function Field({
  label,
  id,
  children,
}: {
  label: string;
  id: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div>
      <label
        htmlFor={id}
        className="muted"
        style={{
          fontSize: 11,
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontWeight: 600,
          display: "block",
          marginBottom: 4,
        }}
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function Item({ a }: { a: AnnotationResponse }): JSX.Element {
  return (
    <li className="card" style={{ padding: "10px 14px" }}>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 4,
        }}
      >
        <span style={{ fontWeight: 600, fontSize: 13 }}>
          <span className="pill pill-person" style={{ marginRight: 8 }}>
            {a.op}
          </span>
        </span>
        <span className="faint" style={{ fontSize: 11 }}>
          #{a.id} · {a.user} · {a.ts.slice(0, 19).replace("T", " ")}
        </span>
      </div>
      <pre
        style={{
          margin: 0,
          fontFamily: "var(--font-mono)",
          fontSize: 11,
          background: "var(--bg-sunken)",
          padding: 8,
          borderRadius: "var(--r-sm)",
          overflowX: "auto",
          color: "var(--muted)",
        }}
      >
        {JSON.stringify(a.payload, null, 2)}
      </pre>
    </li>
  );
}
