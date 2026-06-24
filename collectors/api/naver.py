"""네이버 쇼핑 검색 API 수집기.

docs: https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md
GET https://openapi.naver.com/v1/search/shop.json
headers: X-Naver-Client-Id, X-Naver-Client-Secret
"""
import datetime
import os
import time

import requests
from dotenv import load_dotenv

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

load_dotenv()

ENDPOINT = "https://openapi.naver.com/v1/search/shop.json"
CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")

QUERIES = [
    # 괴수/공룡/특촬 중점
    "소프비 괴수",
    "소프비 고질라",
    "소프비 울트라맨",
    "소프비 공룡",
    "소프비 가면라이더",
    "괴수 소프비",
    "공룡 소프비",
    # 전체 (다른 분야 포함)
    "소프비",
    "소프비 피규어",
    # ── 한일 겹침 정렬 (아미아미 라인과 동일 제품 노림, amiami.py와 KEEP IN SYNC) ──
    "다이나제논 소프비",
    "그리드맨 소프비",
    "괴수8호 소프비",
    "무비몬스터 고질라",
    "신고질라 소프비",
    "고질라 마이너스원",
    "제일복권 소프비",
    "이치방쿠지 소프비",
    "빅소프비 울트라맨",
    "엑스플러스 고질라",
]
DISPLAY = 100          # 최대 100
MAX_PAGES = 10         # query당 최대 1000건 (start 상한 1000)
SORT = "sim"
REQUEST_DELAY = 0.3    # rate limit 배려


def _headers():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise RuntimeError("NAVER_CLIENT_ID / SECRET 미설정 (.env 확인)")
    return {
        "X-Naver-Client-Id": CLIENT_ID,
        "X-Naver-Client-Secret": CLIENT_SECRET,
    }


def search(query, start=1, display=DISPLAY, sort=SORT):
    params = {"query": query, "display": display, "start": start, "sort": sort}
    r = requests.get(ENDPOINT, headers=_headers(), params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    for q in queries:
        page_total = 0
        for page in range(MAX_PAGES):
            start = page * DISPLAY + 1
            if start > 1000:
                break
            data = search(q, start=start)
            items = data.get("items", [])
            if not items:
                break
            for it in items:
                f = extract_fields(it.get("title", ""))
                lprice = it.get("lprice")
                price = float(lprice) if lprice not in (None, "", "0") else None
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "naver",
                        it.get("productId"),
                        f["title"],
                        f["character"],
                        f["genre"],
                        f["maker"],
                        f["line"],
                        f["scale"],
                        f["condition"],
                        price,
                        "KRW",
                        price,  # 이미 KRW
                        0,      # 호가
                        f["is_noise"],
                        it.get("mallName"),
                        " > ".join(filter(None, [it.get("category1"), it.get("category2"),
                                                 it.get("category3"), it.get("category4")])),
                        it.get("link"),
                        it.get("image"),
                        q,
                        now,
                    ),
                )
                page_total += 1
            conn.commit()
            time.sleep(REQUEST_DELAY)
            # 마지막 페이지면 중단
            if start + DISPLAY > data.get("total", 0):
                break
        print(f"[naver] '{q}' -> {page_total} rows")
        total += page_total

    conn.close()
    print(f"[naver] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
