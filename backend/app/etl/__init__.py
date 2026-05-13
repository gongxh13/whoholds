"""ETL package.

Modules:
- pull_top10:     stock_gdfx_top_10_em / stock_gdfx_free_top_10_em → holdings.db
- pull_prices:    stock_zh_a_hist_tx (Tencent source!) → prices.db
- pull_teamwork:  stock_gdfx_holding_teamwork_em → entities.db (raw teamwork rows)
- ingest_teamwork: explode teamwork rows into holder_companies + coholder_pairs
- pull_wikidata:  Wikidata SPARQL for known individual shareholders → wd_cache.db
- disambiguate:   Layer 2 algorithm — rebuild entity + appearance_entity
- bootstrap:      orchestrate the Day-0 full pull

ETL deps (akshare, pandas) are an *optional* extras install — see pyproject
[project.optional-dependencies].etl. Importing this package does NOT import
akshare; each ETL module imports lazily.
"""
