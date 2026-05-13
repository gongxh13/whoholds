import { SearchBox } from "@/components/SearchBox";
import { ThemeToggle } from "@/components/ThemeToggle";
import type { ReactNode } from "react";

/** Header + scrollable main. Used by every page that's not the bare landing. */
export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--fg)" }}>
      <header
        style={{
          background: "var(--bg-elev)",
          borderBottom: "1px solid var(--line)",
          padding: "10px 20px",
          display: "flex",
          gap: 14,
          alignItems: "center",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        <a href="#/" style={{ fontWeight: 700, color: "var(--fg)", textDecoration: "none" }}>
          <b>whoholds</b>{" "}
          <span style={{ fontWeight: 400, color: "var(--muted)" }}>· A 股股东网络</span>
        </a>
        <nav style={{ display: "flex", gap: 4 }}>
          <NavLink href="#/discover">发现</NavLink>
        </nav>
        <SearchBox />
        <ThemeToggle />
      </header>
      <main style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 20px" }}>{children}</main>
    </div>
  );
}

function NavLink({ href, children }: { href: string; children: ReactNode }): JSX.Element {
  return (
    <a
      href={href}
      style={{
        color: "var(--muted)",
        padding: "6px 12px",
        borderRadius: 6,
        fontSize: 13,
        textDecoration: "none",
      }}
    >
      {children}
    </a>
  );
}
