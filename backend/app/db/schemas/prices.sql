CREATE TABLE IF NOT EXISTS stock_daily_price (
    stock_code TEXT,
    date       TEXT,
    adjust     TEXT,
    open       REAL,
    close      REAL,
    high       REAL,
    low        REAL,
    PRIMARY KEY (stock_code, date, adjust)
);

CREATE INDEX IF NOT EXISTS idx_price_stock_date ON stock_daily_price(stock_code, date);
