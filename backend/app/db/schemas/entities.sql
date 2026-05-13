CREATE TABLE IF NOT EXISTS entity (
    entity_id        INTEGER PRIMARY KEY,
    canonical_name   TEXT,
    raw_name         TEXT,
    confidence_level TEXT,
    evidence         TEXT,
    wikidata_qid     TEXT,
    manual_override  INTEGER DEFAULT 0,
    updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS appearance_entity (
    stock_code  TEXT,
    holder_name TEXT,
    entity_id   INTEGER REFERENCES entity(entity_id),
    PRIMARY KEY (stock_code, holder_name)
);

CREATE TABLE IF NOT EXISTS holder_companies (
    holder_name TEXT,
    holder_type TEXT,
    stock_code  TEXT,
    stock_name  TEXT,
    report_date TEXT,
    PRIMARY KEY (holder_name, stock_code)
);

CREATE TABLE IF NOT EXISTS coholder_pairs (
    holder_a       TEXT,
    holder_a_type  TEXT,
    holder_b       TEXT,
    holder_b_type  TEXT,
    co_count       INTEGER,
    company_list   TEXT,
    PRIMARY KEY (holder_a, holder_b)
);

CREATE TABLE IF NOT EXISTS user_annotation (
    id      INTEGER PRIMARY KEY,
    op      TEXT,
    payload TEXT,
    user    TEXT,
    ts      TEXT
);

CREATE INDEX IF NOT EXISTS idx_ae_holder  ON appearance_entity(holder_name);
CREATE INDEX IF NOT EXISTS idx_ae_entity  ON appearance_entity(entity_id);
CREATE INDEX IF NOT EXISTS idx_hc_holder  ON holder_companies(holder_name);
CREATE INDEX IF NOT EXISTS idx_hc_stock   ON holder_companies(stock_code);
CREATE INDEX IF NOT EXISTS idx_cp_a       ON coholder_pairs(holder_a);
CREATE INDEX IF NOT EXISTS idx_cp_count   ON coholder_pairs(co_count);
