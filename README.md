# whoholds

A 股上市公司前十大股东网络与时间线分析工具 —— **开源 (MIT)**。

数据每周一夜由 GitHub Actions 自动跑 ETL，重发 Release 快照；本地一行 `snapshot pull`
就能拿到完整数据集（~510 MB）开始用。

**唯一权威设计**：[`docs/designs/agents/shareholder-network/design.md`](docs/designs/agents/shareholder-network/design.md)。

---

## ⚠️ 重要免责（请先读完再用）

- 工具核心算法之一是 **Layer 2 同名消歧**：根据"共同协同股东"信号把多家公司里的同名持股聚合到
  同一个 entity 桶（详见 design.md §同名消歧算法）。
- **算法不保证 100% 准确**。"张三 #1 持有 13 家公司" 这种聚合结果可能是错的（false-positive）：
  几个同名的不同自然人被算法误并。
- 把**这种系统判断**当作"事实"展示出去，错判时**名誉 / 合规风险归发布者**。如果你把项目部署
  公网或截图分享，请自负后果。
- 原始持股数据来自 [AKShare](https://akshare.akfamily.xyz/) 抓 Eastmoney 公开披露 ——
  "某公司 top10 包含 X" 是公开事实；但"X 持有 N 家公司"是项目新增的聚合视角。
- 工具内置 `user_annotation` 表，提供 merge / split / 绑定 Wikidata QID 的人工纠错能力。
  建议公开实例都开启 basic auth（见下 Docker 部署）。

---

## 快速开始

需要本机已有：
- **Python 3.11+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**（Python 包管理）
- **[pnpm](https://pnpm.io/installation)**（前端构建）
- **[gh CLI](https://cli.github.com/)**（拉 Release 数据，可选）
- 系统包：**zstd**（Snapshot 压缩用，`brew install zstd` / `apt-get install zstd`）

四行起飞：

```bash
git clone https://github.com/gongxh13/whoholds && cd whoholds
python run.py setup           # 装依赖 + 建 DB + 拉 Release 数据 (~10 min)
python run.py up              # 起 backend:8000 + frontend:5174，Ctrl-C 一起退
# 浏览器打开 http://localhost:5174/
```

`setup` / `up` 是聚合命令；细粒度命令也保留（`install` / `migrate` / `snapshot pull`
/ `dev`），见 `python run.py --help`。

> Windows：直接在 PowerShell / cmd 里 `python run.py ...`，不需要 WSL 或 Make。

### 数据更新

数据由 **GitHub Actions 每周一 21:00（北京）** 自动重生成并发到 `data-snapshot` release。
本地跟新只需一行 cron：

```cron
# 每周二 09:00 拉最新 hot 分片（~54 MB，~10 秒）
0 9 * * 2  cd ~/whoholds && python run.py snapshot pull --hot
```

详细机制见 [`docs/designs/agents/periodic-etl-refresh/design.md`](docs/designs/agents/periodic-etl-refresh/design.md)。

### 离线 / 自建数据

不想用 Release 数据（或者数据源 GFW 不通）：

```bash
python run.py migrate
python run.py bootstrap       # 本机跑全量 ETL，≈ 6-12 小时，需要 AKShare 可达
```

或者历史回填：

```bash
python run.py backfill --start-year 2021 --end-year 2025    # ~5h
```

---

## Docker 部署

Compose 自带 Caddy basic auth，开箱即用。详细见 [`deploy/README.md`](deploy/README.md)：

```bash
# 1. 生成 basic auth 凭据
docker run --rm caddy:2.8-alpine caddy hash-password

# 2. 写 .env
cat > .env <<EOF
WHOHOLDS_USER=team
WHOHOLDS_PASS_HASH=<上一步的哈希>
EOF

# 3. 起容器
docker compose up -d --build

# 4. 容器内拉 Release 数据
docker compose exec backend python /app/scripts/restore_snapshot.py --repo gongxh13/whoholds
```

打开 `http://<server-ip>/`，basic auth 进入。

> **生产部署的数据保鲜由 GitHub Actions 兜底**（每周一夜重发 release）。
> 容器内 APScheduler **默认关闭**（避免和 release 数据 diverge）。
> 真要本机自己跑增量 ETL，启动时设 `WHOHOLDS_ENABLE_SCHEDULER=1`。

---

## 开发命令

```bash
python run.py test             # backend pytest + frontend vitest
python run.py lint             # ruff + biome + tsc
python run.py clean -y         # 删 backend/data/

python run.py snapshot --help  # build / pull / roll-year
python run.py refresh --help   # 周度增量（GH Actions 用，本机也可手跑）
python run.py backfill --help  # 历史回填指定年份
python run.py --help
```

测试时 `WHOHOLDS_DISABLE_SCHEDULER=1` 已在 `tests/conftest.py` 自动设。

---

## Project layout

```
backend/        FastAPI + APScheduler + 5 个 SQLite（按读写模式拆）
frontend/       Vite + React 18 + TS strict + Biome + TanStack + ECharts
deploy/         Caddyfile + 部署文档
docs/designs/   设计文档（agents/<topic>/design.md = 真相之源；humans/ = HTML 摘要）
run.py          跨平台入口
.github/        weekly-refresh.yml（每周一自动 ETL → 发 release）
```

更多技术约定 / 测试 / 排坑见 [`AGENTS.md`](AGENTS.md)（所有 coding agent 都读这一份）。

---

## License

MIT — 见 [`LICENSE`](LICENSE)。

Copyright (c) 2026 alex.chen7ac
