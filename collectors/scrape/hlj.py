"""HLJ(HobbyLink Japan) 수집기 — 해외(일본발 직구) **새제품 정가**.

아미아미와 같은 "일본 새제품 정가" 결이지만 다른 소매상 → 정가 표본 보강.
가격이 검색HTML엔 없고 JS로 지연로딩(`/search/livePrice/`)되는 구조라 2단계:
  1. `search/?Word=<kw>&Page=<n>` HTML → 카드별 item_code·이름·url·이미지·상태 + csrf토큰
  2. `search/livePrice/?item_codes=<csv>&csrfmiddlewaretoken=<tok>` JSON(배치)
     → JPYprice(정가 엔화)·release_date·재고상태

평범한 requests.Session으로 통과(CF/인증 불필요). livePrice는 csrf 쿠키+토큰만 있으면 OK.
통화는 JPYprice(엔)로 저장 → amiami/yahoo와 동일 단위, price_krw는 fx로 보정.

  python run.py hlj
"""
import datetime
import html
import re
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.hlj.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept-Language": "en;q=0.9"}

# amiami 영문 라인과 정렬 (KEEP IN SYNC: amiami.py QUERIES)
QUERIES = [
    "godzilla", "ultraman", "kaiju sofubi", "gamera",
    "kamen rider sofubi", "SSSS.GRIDMAN", "SSSS.DYNAZENON", "kaiju no.8",
    "movie monster godzilla", "x-plus godzilla",
]
MAX_PAGES = 3          # query당 최대 72건 (24/page, 보수적)
REQUEST_DELAY = 1.2    # 저빈도 (IP밴 회피)

# 카드 1개 = en_name(코드·이름) … item-img-wrapper(url) … img(src)
_CARD_RE = re.compile(
    r'<input id="en_name_([A-Za-z0-9]+)"[^>]*value="([^"]*)".*?'
    r'item-img-wrapper" href="([^"]+)".*?<img\s*src="([^"]+)"',
    re.S,
)
_CSRF_RE = re.compile(r"csrfmiddlewaretoken': '([^']+)'")


def _jpy_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='JPY' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def _fetch_page(sess, query, page):
    """검색 HTML → (csrf토큰, [(code,name,url,img), ...])."""
    r = sess.get(f"{BASE}/search/", params={"Word": query, "Page": page}, timeout=25)
    r.raise_for_status()
    h = r.text
    tok = _CSRF_RE.search(h)
    cards = _CARD_RE.findall(h)
    return (tok.group(1) if tok else None), cards


def _fetch_prices(sess, codes, token, query):
    """livePrice 배치 → {code: {JPYprice, release_date, stockStatusCode, ...}}."""
    if not codes:
        return {}
    r = sess.get(
        f"{BASE}/search/livePrice/",
        params={"item_codes": ",".join(codes), "csrfmiddlewaretoken": token or ""},
        headers={"X-Requested-With": "XMLHttpRequest",
                 "Referer": f"{BASE}/search/?Word={query}"},
        timeout=25,
    )
    r.raise_for_status()
    try:
        return r.json()
    except ValueError:
        return {}


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _jpy_rate(conn)
    if rate is None:
        print("[hlj] 경고: JPY 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    sess = requests.Session()
    sess.headers.update(HEADERS)
    total = 0

    for q in queries:
        q_total = 0
        for page in range(1, MAX_PAGES + 1):
            try:
                token, cards = _fetch_page(sess, q, page)
            except Exception as e:
                print(f"[hlj] '{q}' p{page} 검색실패: {e} (백오프)")
                time.sleep(3)
                break
            if not cards:
                break
            codes = [c[0] for c in cards]
            try:
                prices = _fetch_prices(sess, codes, token, q)
            except Exception as e:
                print(f"[hlj] '{q}' p{page} livePrice 실패: {e}")
                prices = {}

            for code, name, url, img in cards:
                name = html.unescape(name)
                p = prices.get(code) or {}
                jpy = p.get("JPYprice")
                try:
                    jpy = float(jpy) if jpy not in (None, "") else None
                except (TypeError, ValueError):
                    jpy = None
                price_krw = round(jpy * rate) if (jpy and rate) else None
                f = extract_fields(name)
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "hlj",
                        code,
                        f["title"], f["character"], f["genre"], f["maker"], f["line"],
                        f["scale"], "new",
                        jpy, "JPY", price_krw,
                        0,                              # 새제품 정가/호가
                        f["is_noise"],
                        "HLJ",
                        p.get("stockStatusCode"),
                        BASE + url if url.startswith("/") else url,
                        ("https:" + img) if img.startswith("//") else img,
                        p.get("release_date"),          # 발매(예정)일 "August 2026"
                        q,
                        now,
                    ),
                )
                q_total += 1
            conn.commit()
            time.sleep(REQUEST_DELAY)
        print(f"[hlj] '{q}' -> {q_total} rows")
        total += q_total

    conn.close()
    print(f"[hlj] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
