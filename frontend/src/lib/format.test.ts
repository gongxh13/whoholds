import { describe, expect, it } from "vitest";
import { formatDate, formatPct, formatShares, formatYuan } from "./format";

describe("formatYuan", () => {
  it("uses 亿 for ≥ 1e8", () => {
    expect(formatYuan(1.5e9)).toBe("15.00 亿");
  });
  it("uses 万 for ≥ 1e4 < 1e8", () => {
    expect(formatYuan(50_000)).toBe("5.00 万");
  });
  it("handles null", () => {
    expect(formatYuan(null)).toBe("—");
  });
});

describe("formatShares", () => {
  it("uses 亿股 for ≥ 1e8", () => {
    expect(formatShares(2.5e8)).toBe("2.50 亿股");
  });
});

describe("formatPct / formatDate", () => {
  it("renders 2 decimals", () => {
    expect(formatPct(12.345)).toBe("12.35%");
  });
  it("dashes when invalid date", () => {
    expect(formatDate(undefined)).toBe("—");
  });
  it("hyphenates yyyymmdd", () => {
    expect(formatDate("20240630")).toBe("2024-06-30");
  });
});
