/* Locale-safe formatters. Keep here so every page formats numbers the same. */

export function formatYuan(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)} 亿`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)} 万`;
  return value.toFixed(0);
}

export function formatShares(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${(value / 1e8).toFixed(2)} 亿股`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(2)} 万股`;
  return `${value} 股`;
}

export function formatPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return `${value.toFixed(2)}%`;
}

export function formatDate(yyyymmdd: string | null | undefined): string {
  if (!yyyymmdd || yyyymmdd.length < 8) return "—";
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`;
}
