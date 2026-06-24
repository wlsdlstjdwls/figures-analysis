"""eBay Browse API 수집기 (해외/빈티지 호가 앵커).

docs: https://developer.ebay.com/api-docs/buy/browse/resources/item_summary/methods/search
- OAuth2 Client Credentials grant -> application token
- GET /buy/browse/v1/item_summary/search -> 활성 매물(호가)
- ⚠️ sold(실거래)는 Marketplace Insights = 제한 API (PLAN §10.2). 여기선 Browse 호가만.

키 발급: PLAN §10.2. .env 에 EBAY_APP_ID / EBAY_CERT_ID 입력.

  python run.py ebay   (또는 python -m collectors.api.ebay)
"""
import base64
import datetime
import os
import time

import requests
from dotenv import load_dotenv

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

load_dotenv()

OAUTH_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
SCOPE = "https://api.ebay.com/oauth/api_scope"
MARKETPLACE = "EBAY_US"

APP_ID = os.getenv("EBAY_APP_ID")
CERT_ID = os.getenv("EBAY_CERT_ID")

QUERIES = [
    # 빈티지 소프비 괴수 (해외 거래 활발 세그먼트)
    "vintage sofubi kaiju",
    "godzilla sofubi vinyl figure",
    "ultraman sofubi figure",
    "bullmark godzilla",
    "marusan kaiju",
    "x-plus godzilla sofubi",
    "sofubi soft vinyl figure",
]
LIMIT = 200            # Browse 최대 200/page
MAX_PAGES = 5          # query당 최대 1000건
REQUEST_DELAY = 0.4


def _get_token() -> str:
    if not APP_ID or not CERT_ID:
        raise RuntimeError("EBAY_APP_ID / EBAY_CERT_ID 미설정 (.env 확인, PLAN §10.2)")
    cred = base64.b64encode(f"{APP_ID}:{CERT_ID}".encode()).decode()
    r = requests.post(
        OAUTH_URL,
        headers={"Authorization": f"Basic {cred}",
                 "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": SCOPE},
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _usd_to_krw_rate(conn) -> float | None:
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='USD' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def search(token, query, offset=0, limit=LIMIT):
    r = requests.get(
        SEARCH_URL,
        headers={"Authorization": f"Bearer {token}",
                 "X-EBAY-C-MARKETPLACE-ID": MARKETPLACE},
        params={"q": query, "limit": limit, "offset": offset},
        timeout=25,
    )
    r.raise_for_status()
    return r.json()


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    token = _get_token()
    rate = _usd_to_krw_rate(conn)
    if rate is None:
        print("[ebay] 경고: USD 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    for q in queries:
        page_total = 0
        for page in range(MAX_PAGES):
            offset = page * LIMIT
            data = search(token, q, offset=offset)
            items = data.get("itemSummaries") or []
            if not items:
                break
            for it in items:
                price_obj = it.get("price") or {}
                val = price_obj.get("value")
                cur = price_obj.get("currency", "USD")
                usd = float(val) if val not in (None, "") else None
                # eBay는 USD 외 통화도 올 수 있음 -> USD만 환율 보정, 그 외는 원본만
                if usd is not None and cur == "USD" and rate:
                    price_krw = round(usd * rate)
                else:
                    price_krw = None
                f = extract_fields(it.get("title", ""))
                cats = it.get("categories") or []
                category = cats[0].get("categoryName") if cats else None
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "ebay",
                        it.get("itemId"),
                        f["title"],
                        f["character"],
                        f["genre"],
                        f["maker"],
                        f["line"],
                        f["scale"],
                        (it.get("condition") or f["condition"]),
                        usd,
                        cur,
                        price_krw,
                        0,            # Browse = 호가
                        f["is_noise"],
                        (it.get("seller") or {}).get("username"),
                        category,
                        it.get("itemWebUrl"),
                        q,
                        now,
                    ),
                )
                page_total += 1
            conn.commit()
            time.sleep(REQUEST_DELAY)
            if offset + LIMIT >= data.get("total", 0):
                break
        print(f"[ebay] '{q}' -> {page_total} rows")
        total += page_total

    conn.close()
    print(f"[ebay] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
