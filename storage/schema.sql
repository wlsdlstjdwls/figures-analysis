-- Phase1 MVP 스키마 (SQLite)

CREATE TABLE IF NOT EXISTS product_listing (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source          TEXT NOT NULL,          -- naver / ebay / ...
    source_item_id  TEXT,                   -- 네이버 productId
    title_raw       TEXT NOT NULL,
    character       TEXT,                   -- 정규화 캐릭터/IP
    genre           TEXT,                   -- 괴수 / 공룡 / 특촬 / 괴물 / 기타
    maker           TEXT,                   -- 제조사 (반다이/X-Plus/마미트...)
    line            TEXT,                   -- 시리즈 (무비몬스터/울트라괴수...)
    scale           TEXT,
    condition       TEXT,                   -- new / used / prize
    price           REAL,                   -- 원본 통화 가격
    currency        TEXT DEFAULT 'KRW',
    price_krw       REAL,                   -- 환율 보정 가격
    is_sold         INTEGER DEFAULT 0,      -- 0=호가, 1=실거래
    is_noise        INTEGER DEFAULT 0,      -- 1=비피규어(악세/케이스 등)
    mall_name       TEXT,                   -- 판매처
    category        TEXT,
    url             TEXT,
    image_url       TEXT,                   -- 썸네일 이미지
    source_date     TEXT,                   -- 원본 날짜(와이스: 낙찰=거래시각 / 진행중=마감예정)
    query           TEXT,                   -- 어떤 검색어로 수집됐나
    collected_at    TEXT NOT NULL,          -- ISO8601
    UNIQUE(source, source_item_id, collected_at)
);

CREATE INDEX IF NOT EXISTS idx_listing_maker  ON product_listing(maker);
CREATE INDEX IF NOT EXISTS idx_listing_line   ON product_listing(line);
CREATE INDEX IF NOT EXISTS idx_listing_char   ON product_listing(character);
CREATE INDEX IF NOT EXISTS idx_listing_genre  ON product_listing(genre);
CREATE INDEX IF NOT EXISTS idx_listing_collected ON product_listing(collected_at);

CREATE TABLE IF NOT EXISTS fx_rate (
    date        TEXT NOT NULL,              -- YYYY-MM-DD
    base        TEXT NOT NULL,              -- USD / JPY
    quote       TEXT NOT NULL DEFAULT 'KRW',
    rate        REAL NOT NULL,              -- 1 base = rate KRW
    PRIMARY KEY (date, base, quote)
);
