import { type SearchResponse, getSearch } from "@/lib/api";
import { useEffect, useRef, useState } from "react";

/** Debounced live-search box used in the header. Hits /api/search. */
export function SearchBox(): JSX.Element {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<SearchResponse>({ people: [], companies: [] });
  const debounce = useRef<number | undefined>(undefined);

  useEffect(() => {
    if (!q.trim()) {
      setResults({ people: [], companies: [] });
      return;
    }
    if (debounce.current) window.clearTimeout(debounce.current);
    debounce.current = window.setTimeout(() => {
      getSearch(q)
        .then(setResults)
        .catch(() => undefined);
    }, 180);
    return () => {
      if (debounce.current) window.clearTimeout(debounce.current);
    };
  }, [q]);

  const close = () => {
    setOpen(false);
    setQ("");
  };

  return (
    <div style={{ position: "relative", flex: 1, maxWidth: 480 }}>
      <input
        type="search"
        placeholder="搜索人名 / 公司名 / 代码 (Ctrl-K)"
        value={q}
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => window.setTimeout(close, 150)}
        style={{
          width: "100%",
          background: "var(--bg)",
          border: "1px solid var(--line)",
          color: "var(--fg)",
          padding: "6px 10px",
          borderRadius: 6,
          fontSize: 14,
        }}
      />
      {open && (results.people.length > 0 || results.companies.length > 0) && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            right: 0,
            background: "var(--bg-elev)",
            border: "1px solid var(--line)",
            borderRadius: 6,
            marginTop: 4,
            maxHeight: 320,
            overflowY: "auto",
            zIndex: 50,
            boxShadow: "0 4px 16px rgba(0,0,0,.1)",
          }}
        >
          {results.companies.length > 0 && (
            <div>
              <Header>公司</Header>
              {results.companies.map((c) => (
                <a
                  key={c.stock_code}
                  href={`#/c/${c.stock_code}`}
                  style={itemStyle}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={close}
                >
                  <span>{c.stock_name}</span>
                  <span style={mutedStyle}>{c.stock_code}</span>
                </a>
              ))}
            </div>
          )}
          {results.people.length > 0 && (
            <div>
              <Header>个人</Header>
              {results.people.map((p) => (
                <a
                  key={p.name}
                  href={`#/p/${encodeURIComponent(p.name)}`}
                  style={itemStyle}
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={close}
                >
                  <span>{p.name}</span>
                  <span style={mutedStyle}>
                    {p.n_companies != null ? `${p.n_companies} 家` : ""}
                  </span>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

const itemStyle: React.CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  padding: "6px 10px",
  color: "var(--fg)",
  textDecoration: "none",
};
const mutedStyle: React.CSSProperties = { color: "var(--muted)", fontSize: 12 };

function Header({ children }: { children: string }): JSX.Element {
  return (
    <div
      style={{
        padding: "4px 10px",
        fontSize: 11,
        color: "var(--muted)",
        background: "var(--bg)",
        textTransform: "uppercase",
      }}
    >
      {children}
    </div>
  );
}
