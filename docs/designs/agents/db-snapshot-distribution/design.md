---
topic: db-snapshot-distribution
title: 数据库快照分发（按年分片 + GitHub Release）
status: validated
created: 2026-05-15
spike_dir: .spike/db-snapshot-distribution/
related_code: []
human_summary: ../../humans/db-snapshot-distribution/index.html
---

# 数据库快照分发（按年分片 + GitHub Release）

## What this is

把已经跑完 Day-0 全量 bootstrap 的本机数据集（5 个 SQLite，合计 3.5 GB raw）
打包成可下载的快照，让团队 / 朋友新机器在 < 10 分钟内拿到完整环境，
不必再跑一遍 10 小时的 ETL。**验证完成**：分片策略 + 压缩比 + 合并链路实测可行；
完整发布尺寸 ≈ 510 MB，分 5 个 GitHub Release 附件托管。

## Goal & context

**目标**：消除"新人首次跑要 10h ETL"的体验断点；让数据 baseline 可分享、可版本化。

**为什么现在做**：Day-0 数据本机已经跑完一次（2026-05-14），三五个人圈子要陆续用。

**约束**：
- CLAUDE.md "工具面向小团队 / 朋友圈使用、不部署到公网"
- CLAUDE.md "5 个库不要 ATTACH 在一起"（运行时多库联合查询禁止）
- 仓库分发对象是开发者朋友（能跑命令），不是非技术终端用户

**Scope in**：
- 打包脚本（按年切 prices + 一锅 core）
- 拉取脚本（GitHub Release download + 解压 + 合并）
- 跨年滚动（2027 年时 hot 归档、新建空 hot）

**Scope out**：
- ETL 数据怎么"周度自动刷新"——见姊妹设计 [`periodic-etl-refresh`](../periodic-etl-refresh/design.md)
- 七牛 / Cloudflare R2 等镜像源（GitHub Release 够用，未来真需要再补）
- 非技术用户的开箱即用（不在 scope）

## Alignment conclusions

- **prices.db 全保留**（不瘦身）。代码当前只查 `close ≤ date LIMIT 1` 一种模式，
  理论可瘦 99% 至 < 10 MB；但用户明确要为未来 K 线视图保留全量。
- **GitHub Release 当托管**。仓库私有也能用（`gh auth login` 或 PAT）。
  单文件 2 GB 上限对最大年片（~245 MB zst）绰绰有余。
- **按年分片** 是唯一支持"增量重传"的策略：历史分片永不变，只有 hot 那档每周重发。
- **运行时代码不动**：依旧单 `prices.db`。ATTACH 只在一次性 build/restore 脚本里用，
  不违反"5 库不 ATTACH"原则。
- **`meta.db` 不分发**：`etl_progress` / `dead_letter` / `alert` 是本机私有进度状态，
  新用户从空 schema 开始。

## What we tried — decision log

**起点**：5 个 SQLite 合计 3.5 GB raw（prices.db 3.2 GB 占 90%）；gzip 后 ~1 GB。

1. **是否瘦 prices** —— 调研发现代码全是 `SELECT close … LIMIT 1`，qfq 列没人读、open/high/low 没人读。可瘦 99%。**用户否决**（保留扩展空间）。
2. **托管渠道** —— 比较 GitHub Release / Cloudflare R2 / 七牛 / 手递手。用户选 GitHub Release（仓库已有、零额外配置、免费）。
3. **分片策略** —— 实测三种：
   - 按市场（sh/sz）：2 文件 1.3 GB / 1.8 GB，**增量不友好**（每天 sh/sz 都得重传）
   - hash `% 4`：4 文件均匀 ~770 MB，**增量不友好**（每天全部 4 个重传）
   - **按年 4 档**：360 MB–975 MB raw，**只有 hot 那档需要重传** ← 选定
4. **压缩** —— 对 2026 年片实测：
   - gzip -9：74 MB → 16.9 MB（22.8%）
   - zstd -19：74 MB → 11.0 MB（14.9%，5 MB/s 太慢，build --all ~20 min 不接受）
   - **zstd -9：74 MB → ~13 MB（~17%，30 MB/s）** ← 选这个，build --all ~3 min
5. **合并方式** —— 实测 `ATTACH + INSERT OR REPLACE` 把 810k 行合进空 db 用 0.8s，
   查询和源 db 完全一致（sh600004 close=8.52 两边相同）。ATTACH 在一次性脚本里
   不违反 CLAUDE.md 约定。
6. **跨年滚动** —— 2027 年来时不要"自动把 hot 切两份"的复杂逻辑；提供
   `python run.py snapshot roll-year` 一键归档。

## The approach

### 分片产物

| 文件 | raw 估算 | zst -9 估算 | 重发频率 |
|------|----------|--------------|----------|
| `prices_2005-2015.db.zst` | ~924 MB | **~138 MB** | 一次性 |
| `prices_2016-2020.db.zst` | ~812 MB | **~121 MB** | 一次性 |
| `prices_2021-2024.db.zst` | ~975 MB | **~145 MB** | 一次性 |
| `prices_2025-2026.db.zst` | ~360 MB | **~54 MB** | **每周（hot）** |
| `core.tar.zst`（entities + holdings + wd_cache，meta 清空） | ~325 MB | **~50 MB** | 跟随 hot |
| **合计** | 3.5 GB | **~510 MB** | — |

### Release 布局

- **Tag**：`data-snapshot`（**单一固定 tag，不每次新建**）
- 5 个附件，名字写死如上
- `--clobber` 覆盖式 upload，hot 重发不留旧版

### 新增脚手架

#### `backend/scripts/build_snapshot.py`

输入：`backend/data/{prices,entities,holdings,wd_cache}.db`
输出：`backend/snapshot/` 下的 5 个 `*.zst`

**关键逻辑**：

```python
YEAR_BUCKETS = [
    ("2005-2015", 20050101, 20151231),
    ("2016-2020", 20160101, 20201231),
    ("2021-2024", 20210101, 20241231),
    ("2025-2026", 20250101, 20261231),  # 当前 hot
]

def build_year_shard(label, start, end):
    out = SNAPSHOT_DIR / f"prices_{label}.db"
    shard = sqlite3.connect(out)
    shard.executescript(PRICES_SCHEMA + "PRAGMA journal_mode=WAL;")
    src = sqlite3.connect("backend/data/prices.db")
    rows = src.execute(
        "SELECT * FROM stock_daily_price WHERE date BETWEEN ? AND ?",
        (str(start), str(end)),
    ).fetchall()
    shard.executemany("INSERT INTO stock_daily_price VALUES (?,?,?,?,?,?,?)", rows)
    shard.commit(); shard.close()
    subprocess.run(["zstd", "-9", "-f", str(out), "-o", f"{out}.zst"], check=True)
    out.unlink()  # 留 .zst，删 .db
```

CLI flags:
- `--hot`：只切 hot 那档（Actions 每周用）
- `--all`：全量切 5 个文件（首次种数据用）

`core.tar.zst` 单独打包：

```python
def build_core():
    tmp = SNAPSHOT_DIR / "core_tmp"; tmp.mkdir(exist_ok=True)
    for name in ("entities", "holdings", "wd_cache"):
        shutil.copy(f"backend/data/{name}.db", tmp / f"{name}.db")
    subprocess.run(["tar", "--zstd", "-cf", "core.tar.zst", "-C", tmp,
                    "entities.db", "holdings.db", "wd_cache.db"], check=True)
```

#### `backend/scripts/restore_snapshot.py`

```python
def restore(year_from: str | None = None, hot_only: bool = False):
    # 1. download from latest release
    targets = ["core.tar.zst"] if not hot_only else []
    for label, _, _ in YEAR_BUCKETS:
        if hot_only and label != "2025-2026": continue
        if year_from and label < year_from: continue
        targets.append(f"prices_{label}.db.zst")
    subprocess.run(["gh", "release", "download", "data-snapshot",
                    "--repo", REPO, "-p", "*.zst", "-D", SNAPSHOT_DIR], check=True)

    # 2. ensure data dir + schemas
    subprocess.run(["python", "scripts/migrate.py"], check=True)

    # 3. restore core (overwrite)
    if not hot_only:
        subprocess.run(["tar", "--zstd", "-xf", "core.tar.zst", "-C", "backend/data/"], check=True)

    # 4. merge prices shards into prices.db
    target = sqlite3.connect("backend/data/prices.db")
    target.executescript(PRICES_SCHEMA + "PRAGMA journal_mode=WAL;")
    for label, _, _ in YEAR_BUCKETS:
        if hot_only and label != "2025-2026": continue
        if year_from and label < year_from: continue
        shard_zst = SNAPSHOT_DIR / f"prices_{label}.db.zst"
        shard_db = SNAPSHOT_DIR / f"prices_{label}.db"
        subprocess.run(["zstd", "-d", "-f", str(shard_zst), "-o", str(shard_db)], check=True)
        target.execute(f"ATTACH DATABASE '{shard_db}' AS src")
        target.execute("INSERT OR REPLACE INTO main.stock_daily_price SELECT * FROM src.stock_daily_price")
        target.execute("DETACH DATABASE src")
        shard_db.unlink()
    target.commit(); target.close()
```

#### `run.py snapshot {build,pull,roll-year}` 顶层入口

- `build [--hot|--all]` → `backend/scripts/build_snapshot.py`
- `pull [--year-from <YYYY>] [--hot]` → `backend/scripts/restore_snapshot.py`
- `roll-year` → 当 hot 跨年时归档：在 `YEAR_BUCKETS` 里把当前 hot 改成不变档，
  追加一个空的新 hot。仅当 12/31 → 1/1 过渡时手动跑一次。

### 首次种数据流程

```bash
# 本机（一次性）
python run.py snapshot build --all                       # 切出 5 个 zst
gh release create data-snapshot backend/snapshot/*.zst \
  --notes "Day-0 baseline 2026-05-15" --repo <owner>/whoholds

# 新用户机器
git clone <owner>/whoholds && cd whoholds && cd backend && uv sync
python scripts/migrate.py
python run.py snapshot pull
python run.py up                                          # 启动 backend + frontend
```

### 跨年滚动

```bash
# 2027 年 1 月某一天，本机跑一次
python run.py snapshot roll-year
# 行为：
#   1. 切出 prices_2025-2026.db.zst 上传到 release（之后不再变）
#   2. 更新 YEAR_BUCKETS 把 ("2025-2026", ...) 改成不变档，append ("2027", 20270101, 20271231)
#   3. 提示用户：core.tar.zst 也跟着重发一次
```

## Open questions & risks

- **历史分片"永不变"假设**：依赖 AKShare 不修复历史数据。设计 doc §行情数据采坑提到
  "~5 万行少量修正可能"。实际上重发也不痛（138 MB 上传 ~30s），但要监控。
- **GitHub CDN 国内速度**：私有仓库 release download 走 codeload.github.com，国内速度
  不稳定（10 Mbps - 100 Mbps）。510 MB 完整下载 1-7 min，可接受。**真需要时**再加七牛镜像。
- **ATTACH 在一次性脚本里**：合规存疑点。CLAUDE.md 禁的是"运行时把 5 库 ATTACH 在一起做联合查询"。
  build/restore 脚手架是离线工具、单线程、跑完即关，不属于运行时多库联合查询。设计已遵守约定，
  实现时不要把 ATTACH 写进 `app.db.connection.py`。
- **zstd CLI 依赖**：build 和 restore 都依赖系统 zstd 命令。Linux apt / macOS brew 装一下即可；
  ubuntu-latest runner 默认就有。`Dockerfile` 里要确认。

## Implementation plan

按顺序：

1. **`backend/scripts/build_snapshot.py`** — 切 5 个分片，CLI flags `--hot` / `--all` / `--core-only`。
   - 含 PRICES_SCHEMA 常量（和 `app/db/schemas/prices.sql` 对齐）
   - 写完跑一次 `--hot`，确认 `prices_2025-2026.db.zst` 体积 ≈ 54 MB
2. **`backend/scripts/restore_snapshot.py`** — `gh release download` + zst 解 + ATTACH merge。
   - 加 `--year-from` / `--hot` / `--from-local <dir>`（后者用于离线测试）
   - 测试：跑一次 `--hot`，验证 merge 后 `SELECT close FROM ... LIMIT 1` 等同源 db
3. **`run.py snapshot {build,pull,roll-year}`** — argparse 子命令，调上面两个脚本。
4. **首次种 release**（手动）：本机切 5 个分片 → `gh release create data-snapshot …`。
5. **README + deploy/README** 加 "新机器首次启动"段：clone → migrate → `snapshot pull` → up。
6. **`roll-year` 的实现** 可以延后到 2026-12 再做，但留空函数 + TODO 注释，避免遗忘。

### 测试要点

- `restore_snapshot` 跑两次（幂等）：第二次不应破坏数据
- 异常路径：release 不存在 / zstd 二进制缺失 / 磁盘空间不足 → 明确错误信息
- 体积冒烟测试：`ls -lh backend/snapshot/` 落定后人工 sanity check
