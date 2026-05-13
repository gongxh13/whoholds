CREATE TABLE IF NOT EXISTS top10_holders (
    stock_code   TEXT,
    stock_name   TEXT,
    report_date  TEXT,
    rank         INTEGER,
    holder_name  TEXT,
    share_type   TEXT,
    holdings     INTEGER,
    pct_total    REAL,
    change_value TEXT,
    change_pct   REAL,
    is_person    INTEGER,
    entity_id    INTEGER,
    PRIMARY KEY (stock_code, report_date, rank)
);

CREATE TABLE IF NOT EXISTS top10_free_holders (
    stock_code    TEXT,
    stock_name    TEXT,
    report_date   TEXT,
    rank          INTEGER,
    holder_name   TEXT,
    holder_nature TEXT,
    share_type    TEXT,
    holdings      INTEGER,
    pct_free      REAL,
    change_value  TEXT,
    change_pct    REAL,
    is_person     INTEGER,
    entity_id     INTEGER,
    PRIMARY KEY (stock_code, report_date, rank)
);

CREATE INDEX IF NOT EXISTS idx_top10_holder        ON top10_holders(holder_name);
CREATE INDEX IF NOT EXISTS idx_top10_holder_date   ON top10_holders(holder_name, report_date);
CREATE INDEX IF NOT EXISTS idx_top10_free_holder   ON top10_free_holders(holder_name);
CREATE INDEX IF NOT EXISTS idx_top10_free_h_date   ON top10_free_holders(holder_name, report_date);
