import { useTheme } from "@/lib/theme";

const LABEL: Record<string, string> = {
  system: "🖥 跟随系统",
  light: "☀ 亮色",
  dark: "🌙 暗色",
};

export function ThemeToggle(): JSX.Element {
  const { pref, cycle } = useTheme();
  return (
    <button
      type="button"
      onClick={cycle}
      title="切换主题"
      style={{
        background: "transparent",
        border: "1px solid var(--line)",
        color: "var(--fg)",
        padding: "4px 10px",
        borderRadius: 6,
        cursor: "pointer",
        fontSize: 12,
      }}
    >
      {LABEL[pref] ?? pref}
    </button>
  );
}
