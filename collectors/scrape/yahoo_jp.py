"""야후옥션 재팬 수집기 — 일본 중고 **실거래(낙찰가)**.

와이스의 일본판. 일본 중고 실거래가 = 직구/매입 원가 추정의 핵심.
- closedsearch (낙찰완료) → is_sold=1 (실거래)  ← 현재 수집

기술: closedsearch 페이지가 Next.js SSR → `<script id="__NEXT_DATA__">` JSON에서
`props.pageProps.initialState.search.items.listing.items[]` 추출.
HTML DOM 파싱 불필요(깨끗한 JSON). 인증 불필요. 통화 JPY → price_krw 환율보정.

⚠️ PayPay플리마켓 매물이 섞여 옴(isFleamarketItem). 둘 다 일본 C2C 거래라 유지.
⚠️ 저빈도·소량 호출(IP밴 회피). 차단 시 백오프.
⚠️ TODO 호가(active): search/search 페이지는 Next.js 아님(__NEXT_DATA__ 없음) →
   별도 DOM 파서 필요. 국내 와이스/번개가 호가는 이미 커버하므로 후순위.

  python run.py yahoo
"""
import datetime
import json
import re
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://auctions.yahoo.co.jp"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept-Language": "ja,en;q=0.8"}
NEXT_RE = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)

# 아미아미 라인과 겹치는 일본어 검색어 (KEEP IN SYNC: amiami.py / bunjang.py)
QUERIES = [
    "ゴジラ ソフビ", "ウルトラマン ソフビ", "仮面ライダー ソフビ", "怪獣 ソフビ",
    "ムービーモンスター ゴジラ", "一番くじ ゴジラ", "X-PLUS ゴジラ",
    "ブルマァク 怪獣", "マルサン 怪獣", "大怪獣 ソフビ",
    "ダイナゼノン ソフビ", "グリッドマン ソフビ", "怪獣8号 ソフビ",
]
N = 100               # page당 (야후 최대 100)
MAX_PAGES = 2         # query당 최대 200건 (보수적)
REQUEST_DELAY = 1.0   # 저빈도 (차단 회피)


def _jpy_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='JPY' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def _fetch_items(query, closed, page=1):
    """closed=True면 낙찰(실거래), False면 진행중(호가). items 리스트 반환."""
    path = "closedsearch/closedsearch" if closed else "search/search"
    b = (page - 1) * N
    r = requests.get(f"{BASE}/{path}", headers=HEADERS,
                     params={"p": query, "va": query, "n": N, "b": b + 1},
                     timeout=20)
    r.raise_for_status()
    m = NEXT_RE.search(r.text)
    if not m:
        return []
    d = json.loads(m.group(1))
    try:
        return d["props"]["pageProps"]["initialState"]["search"]["items"]["listing"]["items"]
    except (KeyError, TypeError):
        return []


def _url(it):
    aid = it.get("auctionId", "")
    if it.get("isFleamarketItem"):
        return f"https://paypayfleamarket.yahoo.co.jp/item/{aid}"
    return f"{BASE}/jp/auction/{aid}"


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _jpy_rate(conn)
    if rate is None:
        print("[yahoo] 경고: JPY 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    for q in queries:
        q_total = 0
        for page in range(1, MAX_PAGES + 1):     # closedsearch=실거래(낙찰)만
            try:
                items = _fetch_items(q, closed=True, page=page)
            except Exception as e:
                print(f"[yahoo] '{q}' p{page} 실패: {e} (백오프)")
                time.sleep(3)
                break
            if not items:
                break
            for it in items:
                jpy = it.get("price")
                try:
                    jpy = float(jpy) if jpy not in (None, "") else None
                except (TypeError, ValueError):
                    jpy = None
                price_krw = round(jpy * rate) if (jpy and rate) else None
                f = extract_fields(it.get("title", ""))
                cond = "used" if (it.get("itemCondition") or "").upper() != "NEW" else "new"
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "yahoo_jp",
                        str(it.get("auctionId")),
                        f["title"], f["character"], f["genre"], f["maker"], f["line"],
                        f["scale"], cond,
                        jpy, "JPY", price_krw,
                        1,                              # closedsearch = 실거래(낙찰)
                        f["is_noise"],
                        "PayPayフリマ" if it.get("isFleamarketItem") else "ヤフオク",
                        (it.get("category") or {}).get("name"),
                        _url(it),
                        it.get("imageUrl"),
                        it.get("endTime"),
                        q,
                        now,
                    ),
                )
                q_total += 1
            conn.commit()
            time.sleep(REQUEST_DELAY)
        print(f"[yahoo] '{q}' -> {q_total} rows")
        total += q_total

    conn.close()
    print(f"[yahoo] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
