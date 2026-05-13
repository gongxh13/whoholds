<!-- Last verified 2026-05-14 — PR 1-12 (per design.md §Implementation plan) all
     landed in this branch. Commands below were executed on that date. Re-run
     /spike-init to refresh. -->

# whoholds — agent guide

A 股上市公司前十大股东网络与时间线分析工具。**唯一权威设计**：
[`docs/designs/agents/shareholder-network/design.md`](docs/designs/agents/shareholder-network/design.md) —
任何架构 / 数据模型 / API contract / 算法层面的问题，先读它。

## Scope & 安全约束（不要破坏）

工具面向 **小团队 / 朋友圈** 使用。不部署到公网。整合后的个人身份不能展示给陌生人 ——
凡是会暴露 "某个人在多家公司持股" 拓扑的 endpoint / 页面，访问层（PR 11 Caddy basic auth）必须在位。
原因：消歧不可能 100% 准确，公网误识别 = 名誉风险 + 合规风险。

## Project layout

```
backend/                 # FastAPI + uvicorn + APScheduler + 5 个 SQLite（按读写模式拆）
  Dockerfile             # 多阶段，uv 构建 → python:3.12-slim 运行时
  app/
    api/                 # health / search / person / company / network / discover / annotation
    db/
      schemas/*.sql      # 5 个库的 CREATE TABLE
      connection.py      # 只读默认（uri=ro），写入显式 read_only=False
      migrations.py      # 幂等 (IF NOT EXISTS)
    models/              # Pydantic 响应模型 → OpenAPI → 前端 codegen
    services/            # heuristics（is_person）/ disambiguate（Layer 2 算法）/ wikidata 缓存读
    etl/                 # pull_top10 / pull_prices(腾讯源!) / pull_teamwork / ingest_teamwork /
                         # pull_wikidata / disambiguate / bootstrap / scheduler(APScheduler)
    main.py              # FastAPI app + lifespan 启动 scheduler；CORS 仅允许 dev 前端
  scripts/migrate.py     # 一次性建 5 个库到 data/
  tests/                 # pytest；conftest.py 把 WHOHOLDS_DATA_DIR 指到 tmp + 关 scheduler
frontend/                # Vite + React 18 + TS strict + Biome + TanStack Query/Table + ECharts
  Dockerfile             # node:20-alpine 构建 → caddy:2.8-alpine 静态托管
  src/
    pages/               # Hello / Discover / Company / Person(Hub+Entity) / Network / Annotations
    components/          # AppShell / SearchBox / DataTable(TanStack) / EChartsWrapper /
                         # ConfidenceBadge / ThemeToggle
    lib/                 # api.ts(strongly-typed) / api-types.ts(openapi-typescript 生成) /
                         # theme.ts(三档主题) / router.tsx(hash 路由) / format.ts / queryClient.ts
  test/setup.ts          # Vitest + jsdom，matchMedia polyfill
  e2e/                   # Playwright golden-path
deploy/                  # Caddyfile (basic auth) + README（部署 / bootstrap / 运维）
docker-compose.yml       # backend + caddy；caddy 持卷 /data 卷给 SQLite
docs/designs/            # spike 产物：agents/<topic>/design.md 是真相之源
```

## Environment setup  ✅ verified 2026-05-14

后端用 **uv**（不要 `pip install`，`requires-python = ">=3.11"`）：

```bash
cd backend
uv sync                              # 默认安装；ETL 任务额外要 akshare:
uv sync --extra etl                  # 拉 akshare + pandas（运行时不需要）
uv run python scripts/migrate.py     # 建 5 个 SQLite 库到 backend/data/（gitignored）
```

前端用 **pnpm**（lockfile = pnpm-lock.yaml，Node 20+/24 已验证）：

```bash
cd frontend
pnpm install --frozen-lockfile
```

DB 路径可通过 `WHOHOLDS_DATA_DIR` 环境变量覆盖（测试就这么做的）。
**测试时务必** `WHOHOLDS_DISABLE_SCHEDULER=1`，否则 lifespan 会启动 APScheduler。

## Running tests  ✅ verified 2026-05-14

```bash
cd backend  && uv run pytest -q       # 9 passed（smoke + disambiguate + annotation）
cd frontend && pnpm test              # 9 passed（vitest: format / ConfidenceBadge）
cd frontend && pnpm e2e               # Playwright golden-path（先 pnpm exec playwright install chromium）
```

## Lint & format / Type checking  ✅ verified 2026-05-14

```bash
cd backend  && uv run ruff check
cd frontend && pnpm check            # biome check src
cd frontend && pnpm typecheck        # tsc --noEmit
cd frontend && pnpm build            # = typecheck + vite build；产物 ~462 kB gzip
```

## Codegen — OpenAPI → TS types

```bash
cd frontend && pnpm gen:api          # 写 frontend/openapi.json + src/lib/api-types.ts
```

后端模型变更后必须重跑，否则 `src/lib/api.ts` 里类型对不上。

## Dev servers

```bash
# 后端
cd backend && uv run uvicorn app.main:app --reload --port 8000
# 前端（端口 5174，因为 5173 被本机另一个进程占着；vite.config.ts 已 strictPort）
cd frontend && pnpm dev
```

前端访问 `http://localhost:5174/`；`/api/*` 经 Vite 代理转 `127.0.0.1:8000`。

**Gotcha — 本机 http_proxy**：用户 shell 设了 `http_proxy=http://127.0.0.1:7897`。
用 curl 探本地服务要加 `--noproxy '*'`，否则走代理拿到 502：

```bash
curl --noproxy '*' http://localhost:5174/api/health
```

## Conventions

- **Python**：3.11+，ruff 默认（line-length 100，select = E F I UP B SIM，ignore E501）。
- **TypeScript**：strict + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` + `verbatimModuleSyntax`；
  `@/*` 路径别名指向 `frontend/src/*`。Biome 双引号、2 空格、trailing-comma all。
- **API 设计**：每个领域一个 `app/api/<name>.py` router，挂在 `/api/<name>`。响应类型必走
  `app/models/`（Pydantic），别在 endpoint 里临时 dict 拼装 —— OpenAPI schema 是前端 codegen 的源。
- **DB 访问**：所有读默认走 `app/db/connection.py:connect(name)`（只读 URI），不要直接
  `sqlite3.connect`。5 个库不要 ATTACH 在一起，分别短连接。
- **测试隔离**：`tests/conftest.py` 通过 env var 把数据目录指到 tmp 并 `WHOHOLDS_DISABLE_SCHEDULER=1`，
  **在 `app.main` 被 import 之前**完成 —— 添加新测试时不要在模块顶层 import app。
- **URL 层级**（前端）：`#/p/<name>` 单桶时直接 entity 视图，多桶时 hub 页；详见 design.md §前端架构。
- **ETL 任务延迟导入 akshare**：`backend/app/etl/*.py` 在函数体里 `import akshare`，
  确保 `pyproject.toml extras=[etl]` 没装时 *请求路径* 依旧能起。
- **prices ETL 必须用腾讯源**：`stock_zh_a_hist_tx`（不是 `stock_zh_a_hist`），
  否则 GFW 截 push2his.eastmoney.com 子域。`pull_prices._no_proxy()` 已经清环境变量。
- **消歧实体写入**：`app/etl/disambiguate.run()` 全量重算 entity + appearance_entity；
  user_annotation POST 后会触发对涉及姓名的增量 recompute（`names=[...]`）。

## Build & misc

- **不要**部署到公网（重申）。生产形态：Docker Compose + Caddy basic auth，单机 2C2G（PR 11）。
- **没有 CI**：PR 之前自己跑齐 `uv run pytest` + `uv run ruff check` + `pnpm check` + `pnpm build`。
- **设计文档优先**：`docs/designs/agents/shareholder-network/design.md` 是 12 PR 的实现计划 +
  spike 决策日志 + 同名消歧 / 数据模型 / API 全集。`docs/designs/humans/...` 是给人看的摘要 HTML。
