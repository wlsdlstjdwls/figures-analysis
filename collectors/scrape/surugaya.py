"""駿河屋(Surugaya) 스크래퍼 — Phase2 실거래/일본 시세 (실험적).

주의:
- 정식 API 아님. HTML 스크랩 → 사이트 구조 변경 시 깨짐.
- 보수적 rate limit (요청 간 2초+). 공격적 수집 금지(IP밴 위험, PLAN §3.1).
- 통화 JPY → price_krw는 fx_rate(JPY) 조인으로 보정.
- 무거운 스크랩은 전용 서버 권장(원격 루틴 부적합).

검색: https://www.suruga-ya.jp/search?search_word=<kw>
"""
import time
import datetime

import requests
from bs4 import BeautifulSoup

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.suruga-ya.jp/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (figures-analysis research bot; contact: set-your-email)",
    "Accept-Language": "ja,en;q=0.8",
}
DELAY = 2.5  # 초, 보수적


def latest_jpy_krw(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='JPY' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row["rate"]) if row else None


def fetch(search_word, page=1):
    params = {"search_word": search_word, "page": page}
    r = requests.get(BASE, headers=HEADERS, params=params, timeout=25)
    r.raise_for_status()
    return r.text


def parse(html):
    """상품 카드 파싱. 셀렉터는 사이트 변경 시 조정 필요."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for box in soup.select("div.item, div.search_result_item, p.title"):
        a = box.select_one("a")
        title = a.get_text(strip=True) if a else None
        link = a["href"] if a and a.has_attr("href") else None
        price_el = box.select_one(".price, .item_price, .text-price")
        price_jpy = None
        if price_el:
            digits = "".join(ch for ch in price_el.get_text() if ch.isdigit())
            price_jpy = int(digits) if digits else None
        if title and price_jpy:
            items.append({"title": title, "price_jpy": price_jpy, "url": link})
    return items


def collect(search_words=("ソフビ 怪獣", "ゴジラ ソフビ"), max_pages=1):
    init_db()
    conn = get_conn()
    jpy = latest_jpy_krw(conn)
    if jpy is None:
        print("[surugaya] fx_rate(JPY) 없음 → 먼저 python run.py fx")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0
    for kw in search_words:
        for page in range(1, max_pages + 1):
            html = fetch(kw, page)
            items = parse(html)
            for it in items:
                f = extract_fields(it["title"])
                price_krw = round(it["price_jpy"] * jpy) if jpy else None
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    ("surugaya", it.get("url"), f["title"], f["character"], f["genre"],
                     f["maker"], f["line"], f["scale"], f["condition"],
                     it["price_jpy"], "JPY", price_krw, 0, f["is_noise"],
                     None, None, it.get("url"), kw, now),
                )
                total += 1
            conn.commit()
            time.sleep(DELAY)
        print(f"[surugaya] '{kw}' -> {total} rows so far")
    conn.close()
    print(f"[surugaya] done. {total} rows")


if __name__ == "__main__":
    collect()
