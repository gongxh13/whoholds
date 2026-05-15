# whoholds

A 股上市公司前十大股东网络与时间线分析工具。

**唯一权威设计**：[`docs/designs/agents/shareholder-network/design.md`](docs/designs/agents/shareholder-network/design.md)

⚠️ **不要部署到公网**。整合后的个人身份不能展示给陌生人 —— 见 design.md §合规。

## 两条独立路径

### 一、本地开发（任何平台）

`run.py` 跨平台 —— 只要装了 [uv](https://docs.astral.sh/uv/) 和 [pnpm](https://pnpm.io/)，Mac / Linux / Windows 命令一致。

```bash
python run.py install          # uv sync (含 etl extras) + pnpm install
python run.py migrate          # 建 5 个空 SQLite
python run.py snapshot pull    # 从 GitHub Release 拉数据（推荐：~10 分钟）
python run.py dev              # 并发起后端 8000 + 前端 5174，Ctrl-C 一起退
```

> **不想 / 没条件用 release 数据**？把 `snapshot pull` 换成 `python run.py bootstrap`
> 跑 ≈6 小时本地全量；或者跳过直接 `dev`，UI 会以空状态启动（health 全绿、列表为空）。

**或：** 用 `python run.py snapshot pull --hot` 只拉最近 ~110 MB（hot 年片 + core），
适合"只看近两年"的开发场景。要历史数据再 `--year-from 2005-2015` 一次性拉齐。

打开 `http://localhost:5174/`。

其他命令：

```bash
python run.py test             # backend pytest + frontend vitest
python run.py lint             # ruff + biome + tsc
python run.py clean -y         # 删 backend/data/
python run.py snapshot --help  # build / pull / roll-year
python run.py refresh --help   # 周度增量（GH Actions 用，本机也可手跑）
python run.py --help
```

### 数据如何刷新

- **GitHub Actions 每周一 21:00（北京）** 自动跑 `refresh` → 重切 hot 分片 → 覆盖式上传 release。
  详见 [`docs/designs/agents/periodic-etl-refresh/design.md`](docs/designs/agents/periodic-etl-refresh/design.md)。
- **朋友本地跟新**：每周二早上跑一次（macOS / Linux crontab）：
  ```cron
  0 9 * * 2  cd ~/whoholds && python run.py snapshot pull --hot
  ```
- **首次种数据**（仅 owner，一次性）：本机跑 `python run.py snapshot build --all`
  切出 5 个 zst，然后 `gh release create data-snapshot backend/snapshot/*.zst`。
  之后 Actions 自动维护 hot + core 两个 attachment。

> Windows 用户：上述命令直接在 PowerShell / cmd 里 `python run.py ...` 跑就行；
> 不需要 WSL 或 Make。

### 二、Docker 部署（生产）

详细见 [`deploy/README.md`](deploy/README.md)。要点：

```bash
# 1. 生成 basic auth 哈希
docker run --rm caddy:2.8-alpine caddy hash-password

# 2. 写 .env
echo "WHOHOLDS_USER=team" > .env
echo "WHOHOLDS_PASS_HASH=<上一步的哈希>" >> .env

# 3. 起容器
docker compose up -d --build
```

打开 `http://<server-ip>/`，basic auth 进入。

**首次启动数据**：容器跑起来是空库，需要手动跑一次：

```bash
docker compose exec backend python -m app.etl.bootstrap   # ≈6h
```

**日常增量**：容器内 APScheduler 按 cron 自动跑（每日行情 / 每日 top10 / 季度 teamwork / 每日消歧）。

## Project layout

```
backend/   FastAPI + APScheduler + 5 个 SQLite（独立文件）
frontend/  Vite + React 18 + TS strict + Biome + TanStack + ECharts
deploy/    Caddyfile + 部署文档
docs/      design.md（权威）+ humans/index.html（HTML 摘要）
run.py     本地跨平台入口
```

更多约定 / 测试 / 排坑见 [`AGENTS.md`](AGENTS.md)（所有 coding agent 都读这一份）。

## License

Internal tool — no public license.
