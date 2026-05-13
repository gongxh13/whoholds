# whoholds backend

FastAPI 后端，提供 A 股股东网络与时间线分析 API。

## 开发

```bash
uv sync                          # 安装依赖
uv run python scripts/migrate.py # 创建 5 个 SQLite 库
uv run uvicorn app.main:app --reload --port 8000
```

API 文档：`http://127.0.0.1:8000/docs`（OpenAPI），健康检查：`/api/health`。

## 测试 / Lint

```bash
uv run pytest
uv run ruff check
```

## 结构

```
app/
  main.py          # FastAPI app factory
  config.py        # 5 个 DB 文件路径
  db/
    connection.py  # 每个库一个连接函数
    migrations.py  # 跑 schemas/*.sql
    schemas/*.sql  # 5 个库的建表语句
  models/          # Pydantic 响应模型
  api/             # FastAPI router（每个子领域一个）
  etl/             # 抓取脚本（PR 7 起实现）
tests/             # pytest smoke + contract tests
scripts/migrate.py # 一次性建库
```

5 个 SQLite 库按读写模式拆分（见 `../docs/designs/agents/shareholder-network/design.md`）：
`holdings.db` · `prices.db` · `entities.db` · `wd_cache.db` · `meta.db`，默认放在
`backend/data/`，可通过环境变量 `WHOHOLDS_DATA_DIR` 覆盖。
