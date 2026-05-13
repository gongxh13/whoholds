/* Render a disambiguation confidence label per design.md §同名消歧:
   高置信 / 中置信 / 低置信 / 单飞 — text-only, no percentage. */
import type { ConfidenceLevel } from "@/lib/api";

const STYLE: Record<ConfidenceLevel, { bg: string; fg: string; emoji: string }> = {
  high: { bg: "#dafbe1", fg: "#1a7f37", emoji: "🟢" },
  mid: { bg: "#fff8c5", fg: "#9a6700", emoji: "🟡" },
  low: { bg: "#ffeed5", fg: "#bc4c00", emoji: "🟠" },
  single: { bg: "#eaeef2", fg: "#59636e", emoji: "⚪" },
};

export function ConfidenceBadge({
  level,
  label,
  evidence,
}: {
  level: ConfidenceLevel;
  label: string;
  evidence?: string;
}): JSX.Element {
  const s = STYLE[level] ?? STYLE.single;
  return (
    <span
      title={evidence}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        padding: "2px 8px",
        borderRadius: 6,
        background: s.bg,
        color: s.fg,
        fontSize: 12,
        fontWeight: 600,
      }}
    >
      <span>{s.emoji}</span>
      <span>{label}</span>
      {evidence ? <span style={{ fontWeight: 400, opacity: 0.85 }}>· {evidence}</span> : null}
    </span>
  );
}
