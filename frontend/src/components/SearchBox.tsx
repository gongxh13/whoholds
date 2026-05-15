import { type SearchResponse, getSearch } from "@/lib/api";
import { useEffect, useRef, useState } from "react";

/** Debounced live-search box in the header. Hits /api/search. */
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

  const hasResults = results.people.length > 0 || results.companies.length > 0;

  return (
    <div style={{ position: "relative", width: 360, maxWidth: "40vw" }}>
      <span
        aria-hidden
        style={{
          position: "absolute",
          left: 10,
          top: "50%",
          transform: "translateY(-50%)",
          color: "var(--faint)",
          fontSize: 13,
          pointerEvents: "none",
        }}
      >
        ⌕
      </span>
      <input
        type="search"
        placeholder="搜索人名 / 公司名 / 代码"
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
          padding: "6px 10px 6px 28px",
          height: 32,
          borderRadius: "var(--r-sm)",
          fontSize: 13,
          outline: "none",
          transition: "border-color 0.12s, box-shadow 0.12s",
        }}
        onFocusCapture={(e) => {
          e.currentTarget.style.borderColor = "var(--accent)";
          e.currentTarget.style.boxShadow = "0 0 0 3px var(--accent-bg)";
        }}
        onBlurCapture={(e) => {
          e.currentTarget.style.borderColor = "var(--line)";
          e.currentTarget.style.boxShadow = "none";
        }}
      />
      {open && hasResults && (
        <div
          style={{
            position: "absolute",
            top: "calc(100% + 4px)",
            left: 0,
            right: 0,
            background: "var(--bg-elev)",
            border: "1px solid var(--line)",
            borderRadius: "var(--r)",
            maxHeight: 360,
            overflowY: "auto",
            zIndex: 50,
            boxShadow: "var(--shadow-lg)",
          }}
        >
          {results.companies.length > 0 && (
            <Section title="公司">
              {results.companies.map((c) => (
                <Row
                  key={c.stock_code}
                  href={`#/c/${c.stock_code}`}
                  primary={c.stock_name}
                  secondary={c.stock_code}
                  close={close}
                />
              ))}
            </Section>
          )}
          {results.people.length > 0 && (
            <Section title="个人">
              {results.people.map((p) => (
                <Row
                  key={p.name}
                  href={`#/p/${encodeURIComponent(p.name)}`}
                  primary={p.name}
                  secondary={p.n_companies != null ? `${p.n_companies} 家公司` : ""}
                  close={close}
                />
              ))}
            </Section>
          )}
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div>
      <div
        style={{
          padding: "6px 12px",
          fontSize: 10,
          color: "var(--faint)",
          background: "var(--bg-sunken)",
          textTransform: "uppercase",
          letterSpacing: "0.06em",
          fontWeight: 700,
          borderBottom: "1px solid var(--line-muted)",
        }}
      >
        {title}
      </div>
      {children}
    </div>
  );
}

function Row({
  href,
  primary,
  secondary,
  close,
}: {
  href: string;
  primary: string;
  secondary: string;
  close: () => void;
}): JSX.Element {
  return (
    <a
      href={href}
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "8px 12px",
        color: "var(--fg)",
        textDecoration: "none",
        borderBottom: "1px solid var(--line-muted)",
        transition: "background 0.1s",
      }}
      onMouseDown={(e) => e.preventDefault()}
      onClick={close}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--bg-hover)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
      }}
    >
      <span style={{ fontSize: 13 }}>{primary}</span>
      <span style={{ color: "var(--faint)", fontSize: 12 }}>{secondary}</span>
    </a>
  );
}
