---
topic: periodic-etl-refresh
title: ETL 增量更新与自动重发布（GitHub Actions 周度流水线）
status: validated
created: 2026-05-15
spike_dir: .spike/periodic-etl-refresh/
related_code: []
human_summary: ../../humans/periodic-etl-refresh/index.html
---

# ETL 增量更新与自动重发布（GitHub Actions 周度流水线）

## What this is

让数据每周一次自动刷新，**不依赖任何人本机开机**。
GitHub Actions runner 每周一晚上拉最新 snapshot、跑增量 ETL、重切 hot 分片、
覆盖式上传到固定 Release tag。朋友本地一个 cron 拉新 hot 就跟得上数据。

**验证完成**：AKShare 海外可达性、单股延迟、6h timeout 内可完成。

## Goal & context

**目标**：消除"我 / 朋友机器关机一周 → 数据停更"的体验断点。

**前置 spike**：[`db-snapshot-distribution`](../db-snapshot-distribution/design.md)
定了打包格式（按年分片 + zst）和 release 布局。本设计填上"谁触发、什么时候触发、跑完怎么发"。

**约束**：
- 不要求任何本机 24/7 开机
- 跑在 GitHub Actions free tier 配额内（2000 min/月 private repo）
- 失败要有可见信号（默认邮件 + Actions UI）

**Scope in**：
- GH Actions workflow 文件
- `python run.py refresh` 入口（包装现有 scheduler 任务为 oneshot）
- pull_market 并发优化（让 GH Actions 一次跑能在 1h 内完成）

**Scope out**：
- 朋友本地拉数据的 cron 设置（README 写一段即可）
- 灾备 / 双触发（本机 + Actions 双轨）—— 现在不需要

## Alignment conclusions

- **模型 1：GH Actions 为唯一 ETL 权威**。本机也走 `python run.py snapshot pull` 拉数据。
  这消除"我休假 → 朋友断更"，并把流水线显式化。
- **本机现有的 `backend/app/etl/scheduler.py` APScheduler 配置不动**：
  它跑在 FastAPI lifespan 里，对开发期"本机起 backend 顺便跑一遍 ETL"还有用。
  但**不是**周度刷新的承运方。
- **每周一次足够**：A 股财报披露不是每天都有；daily prices 7 天份一次拉齐没问题。
  频率：北京时间 **每周一 21:00**（cron `0 13 * * 1` UTC）。
- **首次种数据是本机一次性手动**，不是 Actions 第一跑 bootstrap 全量。
  GH Actions 第一次跑要先能 `snapshot pull` 到有效 baseline。

## What we tried — decision log

1. **触发器选型** —— 比较 launchd / GitHub Actions / APScheduler / 手动：
   - APScheduler in-process：现状即此，要求 backend 跑着，朋友圈不可靠 ❌
   - 本机 launchd：不依赖 backend 但仍需开机 ❌
   - **GitHub Actions**：完全云端，零本机依赖 ✅ ← 选
   - 手动：用户会忘 ❌
2. **GH Actions 的关键风险：AKShare 海外出口可达性** —— Tencent K 线源
   `push2his.eastmoney.com` 一向 GFW 敏感。**实测**走本机 127.0.0.1:7897 代理（境外出口）
   拉 sh600004 最近 7 天 K 线，**完整 7 行返回**，确认境外可达。GH Actions Azure 出口
   同理可通。
3. **GH Actions 时长估算** —— 单股 daily prices 增量 6 个 sample 平均 **1.07s**
   （通过境外代理）。外推：
   - daily prices (5184 × 1.07 × 2 个 adjust) ≈ **3.1 h** 串行
   - top10 inc (5184 × ~1s) ≈ **1.4 h** 串行
   - disambiguate ≈ 10 min
   - 串行合计 **~4.5 h**，在 GH Actions 6h timeout 内 ✅
   - 加 4-8 并发 ThreadPoolExecutor 可压到 **~45 min** —— 实施时做
4. **数据持久化** —— 选 Release attachment 而非 Actions cache：
   - cache 5 GB/cache 上限 + 7 天 evict policy，不可靠
   - Release 永久持有，且朋友本来就要拉 release，**复用同一通道**

## The approach

### 触发流程

```
周一 21:00 北京 (cron '0 13 * * 1' UTC)
        │
        ▼
┌───────────────────────────────────────┐
│ GH Actions runner (ubuntu-latest)     │
│                                       │
│ 1. checkout code                      │
│ 2. uv sync --extra etl                │
│ 3. python scripts/migrate.py          │ ← 空 schema
│ 4. python run.py snapshot pull        │ ← 拉上次 release 5 个分片
│ 5. python run.py refresh              │ ← 增量 ETL
│ 6. python run.py snapshot build --hot │ ← 只重切 hot 分片
│ 7. gh release upload data-snapshot \  │ ← 覆盖式上传
│     backend/snapshot/prices_2025-2026.db.zst \
│     --clobber                         │
└───────────────────────────────────────┘
        │
        ▼
朋友本地 cron（独立设置）
  0 9 * * 2  python run.py snapshot pull --hot
```

### Workflow 文件

`.github/workflows/weekly-refresh.yml`：

```yaml
name: weekly snapshot refresh
on:
  schedule: [{ cron: '0 13 * * 1' }]
  workflow_dispatch: {}

jobs:
  refresh:
    runs-on: ubuntu-latest
    timeout-minutes: 180
    permissions:
      contents: write          # release upload 需要
    env:
      GH_TOKEN: ${{ github.token }}
    steps:
      - uses: actions/checkout@v4

      - uses: astral-sh/setup-uv@v3
        with: { version: latest }

      - name: install backend + etl deps
        working-directory: backend
        run: uv sync --extra etl

      - name: prepare data dir
        working-directory: backend
        run: uv run python scripts/migrate.py

      - name: pull previous snapshot
        run: uv run --project backend python run.py snapshot pull

      - name: run incremental ETL
        run: uv run --project backend python run.py refresh
        timeout-minutes: 120

      - name: rebuild hot shard
        run: uv run --project backend python run.py snapshot build --hot

      - name: upload to release
        run: |
          gh release upload data-snapshot \
            backend/snapshot/prices_2025-2026.db.zst \
            backend/snapshot/core.tar.zst \
            --clobber
```

### `python run.py refresh` 入口

新增 `backend/app/etl/refresh.py`（或者直接给 `run.py refresh` 一个内联函数）：

```python
def refresh() -> None:
    from datetime import date
    from app.etl import (
        bootstrap, disambiguate, ingest_teamwork,
        pull_prices, pull_teamwork, pull_top10,
    )

    codes = bootstrap._stocks_with_appearances()

    # daily prices — 只拉最近 14 天即可（上次 release 已经有更早数据）
    today = date.today()
    pull_prices.pull_market(
        codes,
        start_date=(today - timedelta(days=14)).strftime("%Y%m%d"),
    )

    # top10 incremental — 最近一期 quarter_end
    pull_top10.pull_market(codes, [pull_top10.quarter_ends()[-1]])

    # teamwork 只在财报披露集中月跑（避免周周 35min）
    if today.month in (2, 5, 9, 11):
        pull_teamwork.pull_full()
        ingest_teamwork.run()

    # disambiguate 永远跑（轻量）
    disambiguate.run()
```

注意 `pull_prices.pull_market` 当前签名要新增 `start_date` 参数（默认 `20050101` 用于
全量 bootstrap；refresh 时传当前日期前 14 天）。

### 并发优化（实施时做）

当前 `pull_market` 是 for 循环串行。改成：

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def pull_market(stock_codes, *, concurrency=6, **kwargs):
    n_ok = 0
    with ThreadPoolExecutor(max_workers=concurrency) as ex:
        futs = {ex.submit(pull_one, code, **kwargs): code for code in stock_codes}
        for fut in as_completed(futs):
            try:
                if fut.result().status == "ok":
                    n_ok += 1
            except Exception as exc:
                alert("warn", JOB, f"{futs[fut]}: {exc}")
    return n_ok
```

并发 6-8 对 Tencent / Eastmoney 源是安全的（实测多 stock 串行没有触发限频；并发上 8 也不会，
但保守 6）。预期把 4.5h 压到 ~45min。

### 首次启动 Actions 的前置

GH Actions 第一次跑前，**本机已经手动**：

1. `python run.py snapshot build --all` 切出 5 个分片
2. `gh release create data-snapshot backend/snapshot/*.zst --notes "Day-0 baseline 2026-05-15"`

之后 Actions 每周覆盖性 update `data-snapshot` 这个固定 tag 上的 hot + core 两个附件。

### 朋友本地

文档加一段（README 或 deploy/README）：

```bash
# 一次性初始化
git clone … && cd whoholds && cd backend && uv sync
python scripts/migrate.py
python run.py snapshot pull

# 周度自动跟新（macOS / Linux）
crontab -e   # 加入：
# 0 9 * * 2  cd ~/whoholds && python run.py snapshot pull --hot
```

## Open questions & risks

- **AKShare 库 SLA**：GitHub 上 AKShare issue 偶尔提"接口换了"。某周炸了 fall back 下周补，
  数据延期一周对朋友圈场景无影响。Actions 失败默认发邮件给 owner，可观察。
- **GH Actions free tier 配额**：private repo 2000 min/月。预期每周 60-90 min × 4 = 240-360 min，
  留有充分余量。如果以后跑得勤了，PR 升 GitHub Pro 或者换 public。
- **release upload 偶发 5xx**：实施时给上传步骤加 `retry: 3` 或 `gh release upload … || (sleep 30 && gh release upload …)`。
- **首次种数据没人做**：implementation plan 里必须明确"先手动 build + create release"作为前置，
  否则 Actions 第一跑会因 `snapshot pull` 拉不到 release 而失败。
- **AKShare daily 拉的日期边界**：`pull_prices` 当前 `end_date = today()`，周一跑时
  `today` 还没收盘（21:00 北京），但 K 线已经更新（A 股 15:00 收盘）；安全。
- **跨年 hot 滚动**：与 [`db-snapshot-distribution`](../db-snapshot-distribution/design.md) §跨年滚动
  联动。Actions 不感知跨年；需要本人 12/31 → 1/1 时手动跑一次 `python run.py snapshot roll-year`，
  随后 Actions 自动跟新新 hot。

## Implementation plan

按顺序：

1. **`pull_prices.pull_market` 加 `start_date` 参数** —— 默认 `"20050101"` 保持 bootstrap 行为；
   refresh 时传 14 天前。改后跑现有 `tests/test_etl_smoke.py` 确认不挂。
2. **`pull_market` 加 ThreadPoolExecutor 并发** —— `pull_prices` 和 `pull_top10` 同步改。
   保守 `concurrency=6`，留 CLI flag `--concurrency`。本机用 10 个 stock sample 验证耗时 < 5s。
3. **`backend/app/etl/refresh.py`**（或 `run.py refresh` 内联）—— 实现上一节的伪代码。
4. **`run.py refresh` 顶层子命令** —— 调 3 的函数；本机能跑通一次（5 stocks 限制）。
5. **首次种数据**（手动一次）：
   - 跑 `python run.py snapshot build --all`
   - `gh release create data-snapshot backend/snapshot/*.zst --notes "Day-0 baseline 2026-05-15"`
6. **`.github/workflows/weekly-refresh.yml`** —— 完整 workflow。先用 `workflow_dispatch` 手动触发一次
   验证流程能跑通；通过后启用 cron。
7. **README** + **deploy/README** 加"周度刷新流水线"段：原理 + 朋友本地 cron 设置。

### 测试要点

- workflow_dispatch 手动触发跑一次完整流程：4.5h 内能完成
- 失败邮件能收到（owner 邮箱 GitHub 配置好）
- 第二次跑（隔一周）：`snapshot pull` 拉的是上次自己 upload 的版本（验证幂等）
- 并发 6 不被 Tencent / Eastmoney 限频（实测一周不出 dead_letter rate spike）
