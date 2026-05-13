/* Three-state theme (system / light / dark) backed by data-theme.
   - Cycles on toggle, persisted to localStorage.
   - "system" follows prefers-color-scheme; the listener flips the actual class
     when the OS theme changes, so live OS switching works without a reload. */
import { useEffect, useState } from "react";

export type ThemePref = "system" | "light" | "dark";
type Resolved = "light" | "dark";

const KEY = "whoholds.theme";

function readPref(): ThemePref {
  const v = localStorage.getItem(KEY);
  if (v === "light" || v === "dark" || v === "system") return v;
  return "system";
}

function resolve(pref: ThemePref): Resolved {
  if (pref !== "system") return pref;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function apply(pref: ThemePref): void {
  const resolved = resolve(pref);
  document.documentElement.setAttribute("data-theme", resolved);
  document.documentElement.dataset.themePref = pref;
}

export function useTheme(): { pref: ThemePref; resolved: Resolved; cycle: () => void } {
  const [pref, setPref] = useState<ThemePref>(() => readPref());
  const [resolved, setResolved] = useState<Resolved>(() => resolve(pref));

  useEffect(() => {
    apply(pref);
    setResolved(resolve(pref));
    localStorage.setItem(KEY, pref);
    if (pref !== "system") return;
    const m = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => {
      apply("system");
      setResolved(resolve("system"));
    };
    m.addEventListener("change", handler);
    return () => m.removeEventListener("change", handler);
  }, [pref]);

  const cycle = () => {
    setPref((p) => (p === "system" ? "light" : p === "light" ? "dark" : "system"));
  };
  return { pref, resolved, cycle };
}

export function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
