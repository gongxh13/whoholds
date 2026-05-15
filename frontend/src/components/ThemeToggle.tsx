import { useTheme } from "@/lib/theme";

const ICON: Record<string, string> = {
  system: "◐",
  light: "○",
  dark: "●",
};
const TIP: Record<string, string> = {
  system: "跟随系统",
  light: "亮色",
  dark: "暗色",
};

export function ThemeToggle(): JSX.Element {
  const { pref, cycle } = useTheme();
  return (
    <button
      type="button"
      onClick={cycle}
      title={`主题: ${TIP[pref]} (点击切换)`}
      aria-label="切换主题"
      style={{
        background: "transparent",
        border: "1px solid var(--line)",
        color: "var(--fg)",
        width: 32,
        height: 32,
        borderRadius: "var(--r-sm)",
        cursor: "pointer",
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        fontSize: 15,
        lineHeight: 1,
        transition: "background 0.12s, border-color 0.12s",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.background = "var(--bg-hover)";
        e.currentTarget.style.borderColor = "var(--line-strong)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = "transparent";
        e.currentTarget.style.borderColor = "var(--line)";
      }}
    >
      {ICON[pref] ?? "◐"}
    </button>
  );
}
