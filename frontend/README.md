# whoholds frontend

Vite + React 18 + TypeScript (strict) + Biome。

## 开发

```bash
pnpm install
pnpm dev          # http://127.0.0.1:5174  (代理 /api/* → http://127.0.0.1:8000)
pnpm build        # tsc --noEmit + vite build
pnpm check        # biome check
```

后端必须先启动（`cd ../backend && uv run uvicorn app.main:app --reload`），
否则 `/api/health` 走代理会拿到 502。

## 结构

```
src/
  main.tsx          # entry
  App.tsx           # 路由表
  index.css         # CSS 变量 / 主题（PR 4 接 ThemeToggle）
  lib/
    router.tsx      # 极简 hash 路由（PR 6 视情况换 TanStack Router）
    api.ts          # fetch 包装（PR 3 换为 openapi-typescript-codegen）
  pages/            # HelloPage / DiscoverPage / CompanyPage / PersonPage / NetworkPage
  components/       # 通用组件落地于 PR 4+
```

PR 2 只放最小骨架：
- 5 个 page 都是 TODO 占位，正主在 PR 3-5 接入。
- HelloPage 主动 ping `/api/health` 验证前后端打通。
