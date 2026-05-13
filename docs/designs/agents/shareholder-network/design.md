---
topic: shareholder-network
title: A股股东关系网络与时间线分析
status: validated
created: 2026-05-13
spike_dir: .spike/shareholder-network/
related_code: []
human_summary: ../../humans/shareholder-network/index.html
---

# A股股东关系网络与时间线分析

## What this is

一个针对 A 股上市公司"前十大股东"披露数据的本地分析工具：把全市场（沪深京 + 科创北交）历史季报的个人/机构股东抓回来，做四件事 ——
**人物画像**（含 Wikidata 资料 + 跨公司持仓时间线 + 总身价）、**公司股东穿透**（季报切换 + 股权结构变迁堆叠图）、**关系网络**（个人 ↔ 公司、家族 / 一致行动人识别）、**全市场发现**（高频跨公司个人股东榜 + 协同股东对榜）。

Spike 通过 9 个递进实验把数据源、字段、可视化技术选型、市值算法、协同关系挖掘、同名消歧 全部验证完成。受众是小团队 / 朋友圈，本地起 web 服务、加 basic auth 团队使用即可，不做公网产品。

最关键的成果是 **同名消歧算法 Layer 2** 的实证：东财 API 把所有同名股东合并成一条返回（如"吕强 111 家"实际是几十个不同自然人），用"两家公司是否共享非平凡个人协同股东"作为拓扑信号做连通分量，可以把同名股东自动拆成多个候选实体桶，且自动验证了所有已知协同对（吕强+李红、徐国新+陈海华、李欣+周信钢 等）。

## Goal & context

**为什么做这事**：A 股上市公司前十大股东里有大量自然人，公开数据散落在各种渠道、不易系统化分析。要回答"某人在哪些公司持股 / 持仓变化 / 谁是他常见的合伙人 / 他的总身价多少 / 他和谁是家族关系"这类问题，现有 Wind/Choice 等专业终端贵且不灵活，需要一个本地工具。

**核心能力**：
1. 抓取 / 汇总上市公司历史季报前十大股东（个人 + 机构）
2. **个人股东实体识别**（重名拆分） —— 这是项目最核心、最难的工程问题
3. 跨公司 / 跨时间的持仓变化与市值演化
4. 关联关系网络（人 ↔ 公司、家族 / 一致行动人）
5. 外部资料关联（Wikidata 优先，年报董监高简历补充）

**范围**：A 股全市场 + 近 20 年历史；个人股东为主（机构股东作为协同信号），形态为本地 Web 应用（FastAPI + 静态前端，团队内网部署）。

**不在范围内**：港股 / 美股 / 非 A 股；信用 / 评级 / 量化交易策略；公网产品（涉及合规、反爬升级、用户增长等不同问题）。

## Alignment conclusions

跟用户对齐的关键决策（按重要性排序）：

- **受众小团队 / 朋友圈**：需要部署到服务器、加只读 / basic auth；不需要公网注册体系；可以接受"置信度估计"这种不确定输出
- **数据范围全 A 股 + 近 20 年**：数据量大（估算 < 100M 行），SQLite 完全 cope 得住；要工程化批量同步（增量、断点续传、限速）
- **重名问题是核心风险**：A 股个人股东重名极严重；公开字段没有身份证 / 出生年月；100% 准确不可能；**采用"置信度分级 + 实体桶 + 人工修正"混合方案**
- **数据源以 AKShare 为主**：东财源（`stock_gdfx_*` 系列）覆盖最好且免费；行情走腾讯源（东财 `push2his` 子域被 GFW 不稳定）；巨潮兜底
- **形态本地 Python 后端 + 本地 Web 前端**：不做桌面 app、不做 Claude skill；ECharts + FastAPI 已验证
- **"个人股东" 判定三层**：优先流通股东表的"股东性质"字段 → 关键词启发式 → 手工 override 表
- **交互模型采用 4 视图 + 3 铁律**：人物 / 公司 / Ego-Network / 发现 四视图；铁律是 (1) 永远从焦点出发不展示全市场 (2) 网络图节点硬上限 ~100 (3) 全市场分析后端预聚合
- **同名消歧 5 层方案**：Layer 1 锚点 / Layer 2 拓扑（已实证）/ Layer 3 软聚类 / Layer 4 置信度合成 / Layer 5 人工修正
- **置信度文字化**：不写"85%"伪精确数字；改"高置信 · 与李红同公司 10 次"这样有证据的标签
- **URL 层级 Hub / Entity 分离**：`#/p/<name>` 多桶时是 hub 页（只有桶卡片）、`#/p/<name>/<idx>` 是具体实体页（持仓 / 时间线 / 协同），避免汇总数据和拆桶共存的自相矛盾

## What we tried — decision log

按时间顺序，把每个决策点和它的"为什么"留下来：

### 数据源选型

- **Tushare Pro**：`top10_holders` 要 2000 积分以上才能用，5000 积分才舒服。**否决**（积分门槛）
- **AKShare**：`stock_gdfx_top_10_em` / `stock_gdfx_free_top_10_em` 免费、字段稳定、覆盖好。**选定为主源**
- **巨潮资讯**（cninfo）：最权威但只能拿公告 PDF；webapi 反爬严（cookie + enckey）。**留作兜底 / 交叉验证**
- **BaoStock**：财务多但股东数据少。**否决**
- **重大发现**：`stock_gdfx_holding_teamwork_em(symbol='个人')` 是东财的"股东协同分析"，能给出 **1434 个核心个人股东的跨公司持仓聚合** —— 项目"半个爹"，省去自己做实体识别第一步

### 字段意外收获

- `stock_gdfx_free_top_10_em`（前十大流通股东）多一个"股东性质"字段，明确标注"个人 / 证券公司 / 投资基金 / 投资公司 / 其它" —— 直接帮我们解决了"筛选个人股东"的麻烦，**无需自建关键词词典**
- 反例：方洪波（美的董事长）持限售流通A股，不在流通股东表里，LEFT JOIN 后"股东性质"为 NULL → 误判为"其它"
- **结论**：is_person 必须三层判定（流通表字段 → 关键词启发式 → 手工 override）

### 行情数据采坑

- AKShare 默认 `stock_zh_a_hist` 走东财 `push2his.eastmoney.com` 子域：本机被 GFW 截断（TLS 握手后 "Empty reply from server"）
- 同样 akshare、`data.eastmoney.com` 子域却正常 —— 不是整个东财都不通
- **改用 `stock_zh_a_hist_tx` 腾讯源**：4.7s/股票/复权模式，1456 行/6 年，稳定
- 复权选型：**同时存不复权 + 前复权两份**（`adjust` 列）—— 不复权用于"当时市值"展示、前复权用于"持仓真实变化趋势"分析

### 协同分析数据接坑

- `stock_gdfx_holding_teamwork_em(symbol='个人')` 默认是大查询：迭代 1434 个核心个人股东 × ~1.5s = **35 分钟单线程**
- 返回 716,875 条协同关系 / 37,620 个不重复个人股东 / 56,597 行 (holder × company)
- **限制**：每条 record 的"个股详情"字段只给前 10 家（即使 co_count > 10）。我们知道"X 和 Y 在 30 家公司共同出现"，但只知道其中 10 家具体是哪些。如需全集需 stock_gdfx_top_10_em 按需回填
- **限制**：teamwork 接口没有持股数 / 比例 / 市值字段。只有"谁在哪家公司"快照
- **去重坑**：`coholder_pairs` 表里 (A, B) 和 (B, A) 都存在（teamwork 数据本身双向）；ranking 时 `AND holder_a < holder_b`；单人邻居查询时 Python 层 seen set 去重
- **trivial 协同过滤**：HKSCC、香港中央结算、各种 ETF 会和很多人 trivial co-occur，所有人物视角和协同对榜都加 `holder_type='个人' AND coholder_type='个人'` 过滤

### Wikidata 实证 ✓ 同时 ✗

- 头部企业家覆盖好：王传福 Q716030（含化学家+企业家、1966-04-08、雇主=比亚迪、有 zh-wiki）；方洪波、吕向阳、夏佐全都命中
- **重名陷阱完美复现**："黄健"搜出来是韩国人 / 台湾政客 / 1979 年电影演员，没一个是美的高管
- 冷门股东（王念强、栗建伟）完全无 Wikidata 条目
- **结论**：UI 必须显示链接置信度 + 提供手动绑定 QID 机制；Wikidata 命中可能对应"该桶或别桶"，不能盲信

### UX 决策大幅变更

- **v1 原型**：单页全市场网络图。**被用户否决** —— 5000 家公司 × 80 季度直接爆炸
- **v2 重新设计**：4 视图 + 3 铁律（焦点出发 / 节点上限 / 后端预聚合）
- **v2.1 美化**：CSS 变量化、三档主题切换（system/light/dark、`prefers-color-scheme` 自动跟随）、表格通用排序、发现页分页
- **v2.2 市值**：用户问"是不是只有持股数没有市值"。补腾讯源行情、`SUM(holdings × close)` 算总身价
- **v2.3 同名消歧 UI 集成**：用户敏锐问"吕强这种是不是重名严重" → 算法验证 → UI 落地
- **v2.4 Hub/Entity 分离**：用户指出"上面承认 N 个人下面又混着算"的矛盾 → URL 层级化拆 hub 页 + entity 页 + 文字化置信度

### 同名消歧算法验证（最重要的实证）

实验 09 用了"两家公司共享 ≥ 1 个非平凡个人协同股东 → 同实体"作为强联结规则：

| 测试姓名 | 名义公司数 | 拆出桶数 | 最大桶 | 大桶特征 | 判定 |
|---|---|---|---|---|---|
| 吕强 | 111 | 92 | 13 | 李红出现 10 次 | ✅ 拆对，李红是夫妻/亲属候选 |
| 张秀 | 87 | 58 | 28 | 李胜军 / 李光宇 反复出现 | ✅ 与已知"李光宇+李胜军 23 家"协同对吻合 |
| 陈峰 | 56 | 42 | 7 | 无显著大桶 | ✅ 正确识别为 ~40 个不同人 |
| 李欣 | 48 | 24 | 24 | 周信钢反复出现 | ✅ 与已知"周信钢+李欣 28 家"吻合 |
| 徐国新 | 75 | 49 | 25 | 陈海华、张建飞反复出现 | ✅ 与已知"徐国新+陈海华 30 家"吻合 |
| 王传福 | 1 | 1 | 1 | — | ✅ 单实体，不误拆 |

**算法自动识别出所有已知协同对，无需先验知识**。这是该实证最重要的结论。

### 重名陷阱在数据里复现（用户提问导致的核心发现）

用户问"吕强这种是不是重名严重"。用数据反查：
- 吕强协同的 HKSCC 出现 63 家 → 单个真实自然人不可能 63 家走港股通入仓
- "吕"姓内部断崖：吕强 111 / 吕良丰 12 / 第三名 5 → 不是平滑分布
- 全市场 30+ 家公司的"超级股东"几乎全是常见名（张秀、魏巍、陈峰、林新 等）
- **东财 API 自身没字段区分同名不同人**（只有姓名，没 ID） → 我们的爬虫只是忠实存了 API 返回，问题在源头

**这条发现把"重名问题"从理论警告升级为必须立刻处理的产品级风险**，直接驱动了消歧 Layer 2 算法的实现。

## The approach

### 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (TS + React + Vite，static files from FastAPI)    │
│  ├─ pages: Discover / PersonHub / PersonEntity / Company /  │
│  │         Network                                          │
│  └─ libs: theme / chartTheme / format / api(auto-gen)       │
└─────────────────────────────────────────────────────────────┘
                          │ HTTP /api/*
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Backend (FastAPI + uvicorn)                                │
│  ├─ /api/search                                              │
│  ├─ /api/person/{name}[?bucket=N]                            │
│  ├─ /api/person/{name}/disambiguate                          │
│  ├─ /api/company/{code}[?date=YYYYMMDD]                      │
│  ├─ /api/network?focus=...&hops=...&min_pct=...              │
│  └─ /api/discover/{top-cross-holders|top-coholder-pairs}     │
└─────────────────────────────────────────────────────────────┘
                          │
       ┌──────────────────┼──────────────────┐
       ▼                  ▼                  ▼
┌────────────┐    ┌────────────┐    ┌────────────┐
│ holdings   │    │  prices    │    │ entities   │  SQLite (5 files)
│   .db      │    │    .db     │    │    .db     │
└────────────┘    └────────────┘    └────────────┘
       ▲                  ▲                  ▲
       │                  │                  │
┌─────────────────────────────────────────────────────────────┐
│  ETL (APScheduler in FastAPI process)                       │
│  ├─ Initial bootstrap: teamwork(35m) + top10(3h) + prices(3h)│
│  ├─ Daily incremental: prices (mon-fri 18:00)                │
│  ├─ Quarterly incremental: top10 / teamwork (财报季每日)      │
│  └─ Entity disambiguation: daily 04:00                       │
└─────────────────────────────────────────────────────────────┘
```

### 数据模型

5 个独立 SQLite 文件（按读写模式拆分，避免单文件锁争用）：

**`holdings.db`** — 季度持仓数据（~4M 行）

```sql
CREATE TABLE top10_holders (
    stock_code TEXT,        -- 'sh600519' / 'sz000333' / 'bj430718'
    stock_name TEXT,
    report_date TEXT,       -- 'YYYYMMDD'
    rank INTEGER,           -- 1..10
    holder_name TEXT,
    share_type TEXT,        -- '流通A股' / '限售流通A股' / '流通H股'
    holdings INTEGER,
    pct_total REAL,         -- 占总股本%
    change_value TEXT,      -- '+5039970' / '不变' / '新进'
    change_pct REAL,
    is_person INTEGER,      -- -1 unknown / 0 否 / 1 是
    entity_id INTEGER,      -- 消歧后填充，指向 entities.db
    PRIMARY KEY (stock_code, report_date, rank)
);

CREATE TABLE top10_free_holders (
    stock_code TEXT, stock_name TEXT, report_date TEXT, rank INTEGER,
    holder_name TEXT,
    holder_nature TEXT,     -- '个人' / '投资公司' / '证券投资基金' / '证券公司' / '其它'
    share_type TEXT, holdings INTEGER, pct_free REAL,
    change_value TEXT, change_pct REAL,
    is_person INTEGER, entity_id INTEGER,
    PRIMARY KEY (stock_code, report_date, rank)
);

CREATE INDEX idx_top10_holder ON top10_holders(holder_name);
CREATE INDEX idx_top10_holder_date ON top10_holders(holder_name, report_date);
```

**`prices.db`** — 日 K 线（~50M 行，按年分表更佳）

```sql
CREATE TABLE stock_daily_price (
    stock_code TEXT,
    date TEXT,              -- 'YYYYMMDD'
    adjust TEXT,            -- '' (不复权) / 'qfq' (前复权)
    open REAL, close REAL, high REAL, low REAL,
    PRIMARY KEY (stock_code, date, adjust)
);
CREATE INDEX idx_price_stock_date ON stock_daily_price(stock_code, date);
```

**`entities.db`** — 消歧实体 + 协同关系（~10M 行）

```sql
CREATE TABLE entity (
    entity_id INTEGER PRIMARY KEY,
    canonical_name TEXT,    -- "吕强#1"
    raw_name TEXT,          -- "吕强"
    confidence_level TEXT,  -- 'high' / 'mid' / 'low' / 'single'
    evidence TEXT,          -- "与李红同公司 10 次"
    wikidata_qid TEXT,
    manual_override INTEGER DEFAULT 0,
    updated_at TEXT
);

CREATE TABLE appearance_entity (
    stock_code TEXT,
    holder_name TEXT,
    entity_id INTEGER REFERENCES entity(entity_id),
    PRIMARY KEY (stock_code, holder_name)
);

CREATE TABLE holder_companies (    -- 由 teamwork 数据 ETL 而来
    holder_name TEXT,
    holder_type TEXT,
    stock_code TEXT,
    stock_name TEXT,
    report_date TEXT,
    PRIMARY KEY (holder_name, stock_code)
);

CREATE TABLE coholder_pairs (      -- 由 teamwork 协同关系 ETL 而来
    holder_a TEXT,  holder_a_type TEXT,
    holder_b TEXT,  holder_b_type TEXT,
    co_count INTEGER,
    company_list TEXT,             -- 'code|name|YYYYMMDD,...'
    PRIMARY KEY (holder_a, holder_b)
);

CREATE TABLE user_annotation (     -- Layer 5 人工修正
    id INTEGER PRIMARY KEY,
    op TEXT,            -- 'merge' / 'split' / 'bind_qid'
    payload TEXT,       -- JSON
    user TEXT,
    ts TEXT
);

CREATE INDEX idx_ae_holder ON appearance_entity(holder_name);
CREATE INDEX idx_ae_entity ON appearance_entity(entity_id);
CREATE INDEX idx_hc_holder ON holder_companies(holder_name);
CREATE INDEX idx_hc_stock ON holder_companies(stock_code);
CREATE INDEX idx_cp_a ON coholder_pairs(holder_a);
CREATE INDEX idx_cp_count ON coholder_pairs(co_count);
```

**`wd_cache.db`**：Wikidata 资料缓存（< 1 MB）

```sql
CREATE TABLE wd_cache (
    name TEXT PRIMARY KEY,
    qid TEXT, label TEXT, description TEXT,
    birth TEXT, occupations TEXT, employer TEXT, zh_wiki TEXT,
    fetched_at INTEGER
);
```

**`meta.db`**：抓取进度 / ETL 日志 / dead_letter / alert

```sql
CREATE TABLE etl_progress (
    job_name TEXT, key TEXT, status TEXT, attempted_at TEXT, last_error TEXT,
    PRIMARY KEY (job_name, key)
);
CREATE TABLE dead_letter (...);
CREATE TABLE alert (...);
```

### API 设计（已 spike 验证）

详见 `assets/v2-prototype.py` 中的 endpoint 实现。关键 endpoints：

```
GET  /api/search?q=<query>
     → { people: [{name, n_companies?}], companies: [{stock_code, stock_name}] }

GET  /api/person/{name}?bucket=<idx>
     → { name, wikidata, companies[], total_value_series[], coholders[],
         data_source, bucket_meta }
     bucket 给定时：companies / coholders / total_value_series 都按桶过滤

GET  /api/person/{name}/disambiguate
     → { name, total_companies, total_buckets, multi_company_buckets, singletons,
         buckets: [{bucket_idx, size, level, label, evidence, top_peers, companies}],
         singletons_preview: [...] }

GET  /api/company/{code}?date=<YYYYMMDD>
     → { stock_code, stock_name, available_dates[], current_date, top10[], stack_series[] }

GET  /api/network?focus=<name>&hops=<1|2>&min_pct=<float>
     → { nodes[], edges[], focus, stats }

GET  /api/discover/top-cross-holders?limit=N
     → [{ holder_name, n_companies, companies, total_value }]

GET  /api/discover/top-coholder-pairs?limit=N&min_co=3
     → [{ holder_a, holder_b, co_count, company_list }]
```

后端通过 FastAPI 自动生成 OpenAPI schema；前端用 `openapi-typescript-codegen` 自动生成 TS 类型 + client。

### 前端架构

参考 `assets/v2-prototype.py` 中嵌入的 HTML/JS（单文件 ~1300 行），工程化阶段拆为 TS + React 模块。关键架构决策：

- **URL 层级**：
  - `#/discover` — 发现页
  - `#/p/<name>` — 单桶时直接 entity，多桶时 hub 页
  - `#/p/<name>/<bucket_idx>` — 具体实体页
  - `#/c/<stock_code>` — 公司视角
  - `#/n/<name>` — Ego-Network
- **主题**：CSS 变量驱动；`data-theme` 属性三档循环（system / light / dark）；`prefers-color-scheme` 自动跟随；localStorage 持久化；主题切换时所有 ECharts 实例 dispose 重绘
- **图表主题集成**：`getComputedStyle().getPropertyValue('--xxx')` 读 CSS 变量传入 ECharts options
- **通用组件**：`SortableTable` / `PagedTable` / `EChartsWrapper` / `ConfidenceBadge` / `ThemeToggle`

### 同名消歧算法（Layer 2，核心）

**算法**（已在 `assets/disambiguate-algorithm.py` 实现并验证）：

```
对每个姓名 N:
  1. 拿 N 出现的所有公司 C
  2. 对每家公司 c ∈ C，提取 N 的"非平凡个人协同股东集合" S(c)
     - 从 coholder_pairs 拿 (N, peer, company_list)
     - peer 必须是个人（holder_type='个人'）
     - peer 名字不含机构关键词（公司/集团/银行/...）
  3. 建图：节点 = 公司，对每对 (c1, c2) 计算 |S(c1) ∩ S(c2)|
     - 共享 ≥ 1 个非平凡个人协同 → 连边
  4. 并查集找连通分量；每个分量 = 候选实体桶
```

**置信度文字化标签**（不写百分比）：

| 等级 | 触发条件 | 显示 |
|---|---|---|
| 🟢 高置信 | size ≥ 5 且 top_peer_freq ≥ 3 | `高置信 · 与 <peer> 同公司 N 次` |
| 🟡 中置信 | size ≥ 2 且 top_peer_freq ≥ 2 | `中置信 · 与 <peer> 同公司 N 次` |
| 🟠 低置信 | size ≥ 2 且 top_peer_freq < 2 | `低置信 · 仅靠 1 个协同人` |
| ⚪ 单飞 | size = 1 或无个人协同 | `单飞 · 无个人协同信号` |

**复杂度**：O(N²) 公司对，N = 该姓名出现的公司数。吕强 N=111 → 6k 对，跑 0.1 秒。全市场 37k 姓名独立可并行。

**5 层完整方案**（Layer 1/3/4/5 是工程化阶段补的）：

- Layer 1 锚点（高精低召）：Wikidata 命中 + 雇主匹配 / 持股顺位 #1 #2 且 > 5% / 公司年报董监高披露
- Layer 2 拓扑（已实证）：上面那一步
- Layer 3 软聚类：公司行业（申万）+ 注册地 + 时间窗 + 持股顺位相似度 —— 用于拆 Layer 2 的单飞桶
- Layer 4 置信度合成：综合 Layer 1-3 信号合成 0-1 分（仅内部用），UI 用文字化标签
- Layer 5 人工修正：UI 提供合并 / 拆分 / 绑定 QID 操作；标注沉淀进 `user_annotation` 表反哺算法

### "个人股东" 判定（is_person）三层

- 优先：流通股东表 `holder_nature` 字段（最准）
- 回退：关键词启发式 —— 不含 "公司/集团/银行/基金/委员会/中心/合伙/有限/股份/控股/投资/资本/资管/管理/信托/保险/证券/财险/财产/人寿/财务/局/部/协会/工会/LIMITED/NOMINEES/HKSCC" 视为个人
- 修正：`user_annotation` 表里的 manual override

### 抓取细节（避坑）

- AKShare 行情接口：**必须用腾讯源 `stock_zh_a_hist_tx`**（不是默认的 `stock_zh_a_hist`，后者走东财 `push2his` 子域被 GFW 截断）
- 限速：`asyncio.Semaphore(8)` 每域名独立队列
- 重试：tenacity 库，3 次指数退避，最终失败写 `dead_letter` 表
- 失败兜底：股东接口 `data.eastmoney.com` 正常，仅 `push2his` 子域有问题
- 数据校验：每次拉取后 sanity check（行数、字段非空率），异常入 `alert` 表

### 调度（APScheduler）

```python
# 日 K 线：每个交易日 18:00（收盘后）
scheduler.add_job(pull_daily_prices, 'cron',
                  day_of_week='mon-fri', hour=18)

# 前十大股东增量：每天凌晨 2:00 抓新公告
scheduler.add_job(pull_top10_incremental, 'cron', hour=2)

# 协同分析全量：财报季后跑（每季度一次）
scheduler.add_job(pull_teamwork_full, 'cron',
                  month='5,9,11,2', day=15, hour=3)

# 消歧实体重算：每天 04:00
scheduler.add_job(recompute_entities, 'cron', hour=4)
```

A 股财报披露窗口（强相关，加密度抓取）：
- Q1 → 4/30 截止 → 4/15–5/5 每天增量
- Q2 半年报 → 8/31 → 8/15–9/5 每天
- Q3 → 10/31 → 10/15–11/5 每天
- Q4 年报 → 次年 4/30 → 3/15–5/5 每天
- 其余时间每周一次扫盲

## Open questions & risks

### 已知风险（需在工程化阶段处理）

- **重名问题不可能 100% 解决**。Layer 2 把"超级股东"拆开了，但 Layer 3 软聚类没做，84 个"吕强"单飞桶目前无法进一步关联或拆分。需要工程化阶段补 Layer 3（行业 + 地区 + 时间）和 Layer 5（人工修正 UI）
- **协同分析"个股详情"截断**：每条 record 只给前 10 家。"陈海华+徐国新 30 家协同" 我们只知道其中 10 家具体名字。要全集得用 `stock_gdfx_top_10_em` 按需回填，但成本高
- **AKShare 稳定性**：`stock_gdfx_holding_teamwork_em` 实测要 35 分钟；`stock_zh_a_hist` 默认源被 GFW —— 需要主备源切换 + 重试策略
- **GFW 风险**：抓取行情某些子域被截断，腾讯源是当前 workaround。未来可能腾讯源也变化，需要监控告警
- **Wikidata 命中可能错绑**：UI 上必须显示"可能对应该实体或别的同名实体"提示
- **数据时效**：teamwork 数据每季度更新一次；如果用户期望"实时"是错位

### 性能 / 规模风险

- 全市场全历史 20 年抓取按现速估算（单线程）需 ~18 天 → **必须并发 + 增量**。Day 0 拿最近一期 + 行情 + teamwork 可上线（约 6 小时），历史回填 Day 1-7 后台跑
- 全市场消歧重算 37k 名 × ~0.05s ≈ 30 分钟。改成增量（按变化触发）可降到秒级
- SQLite 单写并发是瓶颈 → 5 库拆分 + WAL 模式

### 法律 / 合规

- 数据是公开披露 → 抓取本身合规；但**整合后展示个人身份信息**有边际风险
- 内部使用基本无风险；如果未来公开发布，需要法律审查（特别是把"误识别"展示给陌生人会产生名誉风险）
- 当前方案明确"小团队 / 朋友圈"使用，**通过 basic auth 限制访问者** —— 一定不要把这工具部署到公网注册体系

## Implementation plan

12 个 PR，按依赖顺序：

```
PR  1: backend/ 目录结构 + Pydantic model + OpenAPI schema 落地
       - 把 spike 的 06-app-v2.py 拆成模块化（api / etl / models）
       - 数据库 schema migration 脚本（5 个 SQLite 库）

PR  2: frontend/ 脚手架（Vite + TS + React + 一个 hello world）
       - tsconfig strict、Biome、router.tsx 框架

PR  3: openapi-typescript 接入 + 一个简单页面（如 Company 页）打通端到端
       - 验证类型同步、TanStack Query 用法

PR  4: 把 spike 的 ECharts 配置 + CSS 变量 + 主题切换 搬到 React 组件
       - 抽 EChartsWrapper / ThemeToggle / ConfidenceBadge

PR  5: 五个 page 逐个迁移（discover → company → person hub → entity → network）
       - 每个 PR 一个 page，照着 v2-prototype.py 的实现搬

PR  6: TanStack Table v8 替换自写的 SortableTable / PagedTable
       - 服务端排序 / 分页 通过 URL query 参数

PR  7: 数据抓取脚手架 + 首次 bootstrap 脚本
       - httpx 异步 + Semaphore 限速 + tenacity 重试
       - etl/pull_top10.py / etl/pull_prices.py / etl/pull_teamwork.py
       - 跑通后做 Day 0 全市场 bootstrap

PR  8: 消歧算法 entity 化（生产版）
       - 把 09-disambiguate.py 的算法搬进 etl/disambiguate.py
       - 填充 appearance_entity 表
       - is_person 三层判定逻辑

PR  9: APScheduler 定时任务 + 限速器 + dead_letter / alert 表
       - 财报季加密抓取策略
       - 异常告警（写 meta.db）

PR 10: 用户标注 UI（合并 / 拆分 / 绑定 QID）+ user_annotation 表
       - 标注操作的 audit trail
       - 触发受影响 entity 重算

PR 11: Docker 化 + Caddy basic auth + 部署文档
       - docker-compose.yml + Caddyfile
       - 部署到阿里云 2C2G

PR 12: Vitest 单测覆盖关键逻辑 + Playwright e2e 关键路径
       - 消歧算法测试 / API contract 测试 / 主要 UI 流程 e2e
```

Spike 已经把 PR 1-5 的可行性都验证过（实际 06-app-v2.py 单文件就实现了端到端），PR 6-12 是工程化新工作。

PR 7-8 是真正"决定项目能不能跑起来"的两步：bootstrap 抓数据 + 消歧算法落地。先把这两条打通，UI 层面有最近一期 + 协同分析 + 消歧拆桶可看，团队就能上线。历史回填和精细化打磨可以增量做。

## 参考资源

- `assets/v2-prototype.py` — spike 末态的单文件原型（FastAPI + 嵌入 HTML/JS），可作为各 page / endpoint 的实现参考
- `assets/disambiguate-algorithm.py` — Layer 2 消歧算法独立验证脚本
- AKShare 接口文档：https://akshare.akfamily.xyz/data/stock/stock.html
- Wikidata SPARQL endpoint：https://query.wikidata.org/sparql
- 东方财富股东协同分析页：https://data.eastmoney.com/gdfx/HoldingAnalyse.html
