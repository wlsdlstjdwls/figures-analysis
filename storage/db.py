"""SQLite 연결 + 스키마 초기화."""
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "figures.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_conn():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# 분석/리포트용: 상품(source+source_item_id)별 최신 스냅샷 1건만.
# 같은 상품이 여러 검색어/여러 날 수집돼도 중복 카운트 방지.
# (시계열은 의도적으로 전체 스냅샷을 쓰므로 이 헬퍼를 쓰지 않는다.)
LATEST_LISTINGS_SQL = """
SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY source, source_item_id
        ORDER BY collected_at DESC, id DESC
    ) AS _rn
    FROM product_listing
    WHERE price_krw IS NOT NULL AND is_noise = 0
)
WHERE _rn = 1
"""


def load_latest_df():
    """상품별 최신 스냅샷만 담은 DataFrame 반환 (분석/리포트 공용)."""
    import pandas as pd
    conn = get_conn()
    df = pd.read_sql_query(LATEST_LISTINGS_SQL, conn)
    conn.close()
    return df.drop(columns=["_rn"], errors="ignore")


def init_db():
    conn = get_conn()
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    print(f"[db] initialized at {DB_PATH}")


if __name__ == "__main__":
    init_db()
