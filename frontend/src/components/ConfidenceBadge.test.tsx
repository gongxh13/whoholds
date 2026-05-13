import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBadge } from "./ConfidenceBadge";

describe("ConfidenceBadge", () => {
  it("renders label + evidence + emoji for high", () => {
    render(<ConfidenceBadge level="high" label="高置信" evidence="与李红同公司 10 次" />);
    expect(screen.getByText("高置信")).toBeInTheDocument();
    expect(screen.getByText(/与李红同公司 10 次/)).toBeInTheDocument();
  });

  it("falls back to single style when level is unknown", () => {
    // @ts-expect-error — verifying runtime fallback for stale data
    render(<ConfidenceBadge level="bogus" label="兜底" />);
    expect(screen.getByText("兜底")).toBeInTheDocument();
  });
});
