<!-- Last verified 2026-05-14 — PR 1-12 (per design.md §Implementation plan) all
     landed in this branch. Commands below were executed on that date. Re-run
     /spike-init to refresh. -->

# whoholds — agent guide

A 股上市公司前十大股东网络与时间线分析工具。**唯一权威设计**：
[`docs/designs/agents/shareholder-network/design.md`](docs/designs/agents/shareholder-network/design.md) —
任何架构 / 数据模型 / API contract / 算法层面的问题，先读它。

## Scope & 风险约束（不要破坏）

**开源工具**（MIT），任何人可 clone / fork / 部署。原始持股数据本身就是公开披露的（上市公司
top10 强制披露），代码读 AKShare 公开源。

**真正的风险点是 Layer 2 同名消歧的 false-positive** —— 算法把多家公司里的"张三"
判为同一人，可能是错的。把"系统判断的人物聚合"展示出去，错判时名誉责任归发布者。
所以：
- README 必须保留"消歧 false-positive 免责"段，发布前所有用户能看到。
- 任何用户标注 (`user_annotation`) 必须有 audit trail（`who/op/payload/ts`），已经在
  `entities.user_annotation` 表里；不要拆。
- 后端 `_auth.py` env-gated basic auth 保留作为**可选** hardening，但不强制 —— 开源
  实例随你公网部署，basic auth 由部署者自己决定开不开。
- Docker Compose 的 Caddy basic auth (`deploy/Caddyfile`) 同上：默认配好、便于使用者
  开箱即用，不强制。

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

**APScheduler 默认关闭**（GH Actions 是数据权威）。开发期需要本机自己跑增量 ETL 时设
`WHOHOLDS_ENABLE_SCHEDULER=1`。`WHOHOLDS_DISABLE_SCHEDULER=1` 旧 env 保留兼容（强制关闭，
覆盖 enable）。

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

- **生产形态**：Docker Compose + Caddy（默认 basic auth），单机 2C2G。开源后任何人都可部署，
  basic auth 由部署者自行选择是否开启。
- **GH Actions 是 ETL 权威**：见 `docs/designs/agents/periodic-etl-refresh/design.md`。本地
  APScheduler 默认**关闭**，需要本机自己跑增量时再 `WHOHOLDS_ENABLE_SCHEDULER=1`。这是为了
  避免本地数据和 release 数据 diverge（详见同设计 doc §模型 1）。
- **CI**：`.github/workflows/weekly-refresh.yml` 跑 ETL + 发 release。PR 前手动跑齐
  `uv run pytest` + `uv run ruff check` + `pnpm check` + `pnpm build`。
- **设计文档优先**：`docs/designs/agents/shareholder-network/design.md` 是 12 PR 的实现计划 +
  spike 决策日志 + 同名消歧 / 数据模型 / API 全集。`docs/designs/humans/...` 是给人看的摘要 HTML。
