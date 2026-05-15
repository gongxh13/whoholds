# whoholds — deploy

设计文档：[`docs/designs/agents/shareholder-network/design.md`](../docs/designs/agents/shareholder-network/design.md)

**只部署到内网或带 basic auth 的小团队入口**。合规 / 名誉风险见 design.md §法律。

## 单机 2C2G 部署（阿里云 / 腾讯云 / Hetzner）

### 1. 生成 basic auth 凭据

```bash
docker run --rm caddy:2.8-alpine caddy hash-password
# 输入密码 → 得到 $2a$14$... 哈希
```

写入 `deploy/docker/.env`（compose 文件就在该目录，默认读取本目录的 `.env`）：

```env
WHOHOLDS_USER=team
WHOHOLDS_PASS_HASH=$2a$14$...
```

（仓库根目录有 `.env.example` 可作模板：`cp .env.example deploy/docker/.env` 再改）

### 2. 启动

```bash
# 推荐：通过 run.py 包装（自动 cd 到 deploy/docker）
python run.py up --docker

# 或手动：
cd deploy/docker && docker compose up -d --build
```

容器：
- `backend` — FastAPI + APScheduler（数据存 named volume `whoholds_data`）
- `caddy` — 反向代理 + basic auth + 静态前端

### 3. 首次种数据

容器跑起来是空库，**推荐**从 GitHub Release 拉打包好的快照（~510 MB，5-10 分钟）：

```bash
docker compose exec backend python /app/scripts/restore_snapshot.py --repo <owner>/whoholds
```

如果环境不通 GitHub，或者你就是上传方，回退到本地全量抓取：

```bash
docker compose exec backend python -m app.etl.bootstrap
# ≈6 小时：teamwork (35min) + ingest + disambiguate + top10 + prices + wikidata
```

> ⚠️ bootstrap 需要外网通到 AKShare（data.eastmoney.com）和 Wikidata。
> design.md §抓取细节 提到 push2his.eastmoney.com 子域被 GFW 截断，
> 已用腾讯源（`stock_zh_a_hist_tx`）规避。

### 3.5 周度数据刷新

**生产部署不要靠容器内 APScheduler 维护数据保鲜。** 权威数据由 GitHub Actions
每周一 21:00（北京）自动产出，重切 hot 分片后覆盖式上传到 release。
设计：[`docs/designs/agents/periodic-etl-refresh/design.md`](../docs/designs/agents/periodic-etl-refresh/design.md)。

生产机加一个 crontab 拉新 hot 即可：

```cron
# 每周二 09:00 北京时间拉最新 hot 进容器
0 9 * * 2  docker compose exec backend python /app/scripts/restore_snapshot.py --hot --repo <owner>/whoholds
```

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

- **APScheduler 仍在 backend 容器里**，但**不再是**周度刷新的承运方 —— GitHub Actions 接管了那条线（见上方 §3.5）。容器内的 scheduler 现在主要用于"开发期手动起 backend 顺便补数据"以及临时灾备。
- **SQLite 5 库都在 `/data`** — 备份就备份整卷。
- **不要**开放 8000 端口到公网，所有访问必须经过 Caddy basic auth。
