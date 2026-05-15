/* Minimal hash router — zero dependencies.
   PR 6 may swap this for TanStack Router; for now it's a 60-line shim that
   does what the v2 prototype's #/ scheme needs: matching, params, navigation. */
import { type ReactElement, type ReactNode, useEffect, useState } from "react";

export type RouteParams = Record<string, string>;

interface RouteProps {
  path: string;
  component: (props: { params: RouteParams }) => ReactElement | null;
}

export function Route(_: RouteProps): null {
  return null;
}

interface RouterProps {
  defaultPath: string;
  children: ReactNode;
}

function readHashPath(defaultPath: string): string {
  const raw = window.location.hash.replace(/^#/, "");
  // Strip query string — route matching only looks at the path portion.
  // DataTable writes sort/page state as `#/?cx=…`, which would otherwise
  // never match a route and leave the page blank.
  const pathOnly = raw.split("?")[0] ?? "";
  return pathOnly.length > 0 ? pathOnly : defaultPath;
}

function safeDecode(s: string): string {
  // decodeURIComponent throws URIError on malformed %XX — return raw rather
  // than blank-screen the whole route.
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

function matchRoute(pattern: string, path: string): RouteParams | null {
  const patternParts = pattern.split("/").filter(Boolean);
  const pathParts = path.split("/").filter(Boolean);
  if (patternParts.length !== pathParts.length) return null;
  const params: RouteParams = {};
  for (let i = 0; i < patternParts.length; i++) {
    const pat = patternParts[i] ?? "";
    const seg = pathParts[i] ?? "";
    if (pat.startsWith(":")) {
      params[pat.slice(1)] = safeDecode(seg);
    } else if (pat !== seg) {
      return null;
    }
  }
  return params;
}

export function Router({ defaultPath, children }: RouterProps): ReactElement | null {
  const [path, setPath] = useState<string>(() => readHashPath(defaultPath));

  useEffect(() => {
    const onHash = () => setPath(readHashPath(defaultPath));
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [defaultPath]);

  const routes: ReactElement<RouteProps>[] = [];
  if (Array.isArray(children)) {
    for (const c of children) {
      if (c && typeof c === "object" && "props" in c) {
        routes.push(c as ReactElement<RouteProps>);
      }
    }
  }

  for (const r of routes) {
    const params = matchRoute(r.props.path, path);
    if (params) {
      const Comp = r.props.component;
      return <Comp params={params} />;
    }
  }
  return null;
}

export function navigate(path: string): void {
  window.location.hash = path;
}
