CREATE TABLE IF NOT EXISTS etl_progress (
    job_name     TEXT,
    key          TEXT,
    status       TEXT,
    attempted_at TEXT,
    last_error   TEXT,
    PRIMARY KEY (job_name, key)
);

CREATE TABLE IF NOT EXISTS dead_letter (
    id      INTEGER PRIMARY KEY,
    job     TEXT,
    key     TEXT,
    payload TEXT,
    error   TEXT,
    ts      TEXT
);

CREATE TABLE IF NOT EXISTS alert (
    id        INTEGER PRIMARY KEY,
    severity  TEXT,
    component TEXT,
    message   TEXT,
    ts        TEXT
);
