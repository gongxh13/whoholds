CREATE TABLE IF NOT EXISTS wd_cache (
    name        TEXT PRIMARY KEY,
    qid         TEXT,
    label       TEXT,
    description TEXT,
    birth       TEXT,
    occupations TEXT,
    employer    TEXT,
    zh_wiki     TEXT,
    fetched_at  INTEGER
);
