import { useTheme } from "@/lib/theme";
/* Thin wrapper around echarts-for-react that re-renders when the theme changes
   so chart colors track CSS variables. design.md §前端架构 calls for this
   exact pattern (read CSS vars, pass into options, dispose on theme switch). */
import ReactECharts from "echarts-for-react";

type Props = {
  option: object;
  height?: number | string;
  notMerge?: boolean;
};

export function EChartsWrapper({ option, height = 320, notMerge = true }: Props): JSX.Element {
  const { resolved } = useTheme();
  return (
    <ReactECharts
      key={resolved}
      option={option}
      style={{ height, width: "100%" }}
      notMerge={notMerge}
      theme={resolved === "dark" ? "dark" : "light"}
    />
  );
}
