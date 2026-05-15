# 设计文档索引

每个条目都来自一次 `/spike` 经过 `/spike-wrap` 整合而成。Agent 文档是真相之源，Human 摘要是短版本。

| Topic | Title | Status | Date | Gist | Agent doc | Human doc |
|-------|-------|--------|------|------|-----------|-----------|
| shareholder-network | A股股东关系网络与时间线分析 | validated | 2026-05-13 | A 股全市场前十大股东数据本地分析工具；含同名消歧 Layer 2 拓扑算法 | [design.md](agents/shareholder-network/design.md) | [index.html](humans/shareholder-network/index.html) |
| db-snapshot-distribution | 数据库快照分发（按年分片 + GitHub Release） | validated | 2026-05-15 | 3.5G 数据库切年片 + zst 压成 510MB，5 个 Release 附件托管，朋友 10 min 拉齐数据 | [design.md](agents/db-snapshot-distribution/design.md) | [index.html](humans/db-snapshot-distribution/index.html) |
| periodic-etl-refresh | ETL 增量更新与自动重发布（GitHub Actions 周度流水线） | validated | 2026-05-15 | GitHub Actions 每周一自动跑增量 ETL + 重切 hot + 覆盖式 upload，本机不必开机 | [design.md](agents/periodic-etl-refresh/design.md) | [index.html](humans/periodic-etl-refresh/index.html) |
