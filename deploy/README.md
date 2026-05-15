# whoholds — deploy

设计文档：[`docs/designs/agents/shareholder-network/design.md`](../docs/designs/agents/shareholder-network/design.md)

**只部署到内网或带 basic auth 的小团队入口**。合规 / 名誉风险见 design.md §法律。

## 单机 2C2G 部署（阿里云 / 腾讯云 / Hetzner）

### 1. 生成 basic auth 凭据

```bash
docker run --rm caddy:2.8-alpine caddy hash-password
# 输入密码 → 得到 $2a$14$... 哈希
```

写入 `.env`：

```env
WHOHOLDS_USER=team
WHOHOLDS_PASS_HASH=$2a$14$...
```

### 2. 启动

```bash
docker compose up -d --build
```

容器：
- `backend` — FastAPI + APScheduler（数据存 named volume `whoholds_data`）
- `caddy` — 反向代理 + basic auth + 静态前端

### 3. 首次 bootstrap 数据

容器跑起来是空库，要手动触发一次全量抓取：

```bash
docker compose exec backend python -m app.etl.bootstrap
# ≈6 小时：teamwork (35min) + ingest + disambiguate + top10 + prices + wikidata
```

之后每天 02:00 / 04:00 / 18:00 由容器内 APScheduler 自动增量。

> ⚠️ bootstrap 需要外网通到 AKShare（data.eastmoney.com）和 Wikidata。
> design.md §抓取细节 提到 push2his.eastmoney.com 子域被 GFW 截断，
> 已用腾讯源（`stock_zh_a_hist_tx`）规避。

### 4. 日常运维

```bash
# 查日志
docker compose logs -f backend
docker compose logs -f caddy

# 查 etl_progress / alert
docker compose exec backend python -c "
from app.config import DB_PATHS; import sqlite3
c = sqlite3.connect(f'file:{DB_PATHS[\"meta\"]}?mode=ro', uri=True)
for r in c.execute('SELECT * FROM alert ORDER BY id DESC LIMIT 20'):
    print(r)
"
```

## 注意事项

- **APScheduler 在 backend 容器里跑** — 不要再起一个 worker；single-instance + `coalesce` 在 design.md §调度 已说明。
- **SQLite 5 库都在 `/data`** — 备份就备份整卷。
- **不要**开放 8000 端口到公网，所有访问必须经过 Caddy basic auth。
