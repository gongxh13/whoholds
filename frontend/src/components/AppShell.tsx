import { SearchBox } from "@/components/SearchBox";
import { ThemeToggle } from "@/components/ThemeToggle";
import type { ReactNode } from "react";

/** Sticky header + scrollable main. Used by every page. */
export function AppShell({ children }: { children: ReactNode }): JSX.Element {
  const path = window.location.hash.replace(/^#/, "").split("?")[0] || "/";

  return (
    <div style={{ minHeight: "100vh", background: "var(--bg)", color: "var(--fg)" }}>
      <header
        style={{
          background: "var(--bg-elev)",
          borderBottom: "1px solid var(--line)",
          padding: "0 var(--s-5)",
          height: "var(--header-h)",
          display: "flex",
          gap: 16,
          alignItems: "center",
          position: "sticky",
          top: 0,
          zIndex: 20,
          backdropFilter: "saturate(180%) blur(8px)",
        }}
      >
        <a
          href="#/"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 8,
            color: "var(--fg-strong)",
            textDecoration: "none",
            fontWeight: 700,
            fontSize: 15,
            letterSpacing: "-0.01em",
          }}
        >
          <Logo />
          whoholds
        </a>
        <nav style={{ display: "flex", gap: 2, marginRight: "auto" }}>
          <NavLink href="#/" active={path === "/" || path === "/discover"}>
            发现
          </NavLink>
          <NavLink href="#/annotations" active={path.startsWith("/annotations")}>
            标注
          </NavLink>
          <NavLink href="#/health" active={path.startsWith("/health")}>
            状态
          </NavLink>
        </nav>
        <SearchBox />
        <ThemeToggle />
      </header>
      <main>{children}</main>
    </div>
  );
}

function NavLink({
  href,
  active,
  children,
}: {
  href: string;
  active: boolean;
  children: ReactNode;
}): JSX.Element {
  return (
    <a
      href={href}
      style={{
        color: active ? "var(--accent-fg)" : "var(--muted)",
        background: active ? "var(--accent-bg)" : "transparent",
        padding: "5px 12px",
        borderRadius: "var(--r-sm)",
        fontSize: 13,
        fontWeight: 500,
        textDecoration: "none",
        transition: "background 0.12s ease, color 0.12s ease",
      }}
    >
      {children}
    </a>
  );
}

function Logo(): JSX.Element {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        width: 22,
        height: 22,
        borderRadius: 6,
        background: "linear-gradient(135deg, var(--accent), var(--focus-orange))",
        color: "white",
        fontSize: 11,
        fontWeight: 800,
        letterSpacing: 0,
      }}
    >
      W
    </span>
  );
}
