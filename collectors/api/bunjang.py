"""번개장터 수집기 — 국내 중고 호가.

비공식 내부 API (역분석). 인증 불필요. 가격 단위 KRW.
GET https://api.bunjang.co.kr/api/1/find_v2.json?q=&page=&n=&order=score

필드: pid, name, price, product_image, update_time(unix=등록/갱신), location(지역),
      num_faved(찜), used(중고여부), status. 상세: m.bunjang.co.kr/products/<pid>

PLAN §3 한국 중고. 봇차단·IP밴 위험 → 저빈도·소량(§3.1). 차단 시 백오프.

  python run.py bunjang
"""
import datetime
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

ENDPOINT = "https://api.bunjang.co.kr/api/1/find_v2.json"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

QUERIES = [
    "소프비 괴수", "소프비 고질라", "소프비 울트라맨", "소프비 공룡",
    "소프비 가면라이더", "괴수 소프비", "소프비", "소프비 피규어",
]
N = 100
MAX_PAGES = 5          # query당 최대 500건
REQUEST_DELAY = 0.6    # 보수적 (차단 회피)


def search(query, page=0, n=N):
    params = {"q": query, "order": "score", "page": page, "n": n,
              "stat_device": "w", "version": "4"}
    r = requests.get(ENDPOINT, headers=HEADERS, params=params, timeout=20)
    r.raise_for_status()
    return r.json()


def _iso(unix):
    try:
        return datetime.datetime.fromtimestamp(int(unix)).isoformat(timespec="seconds")
    except Exception:
        return None


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    for q in queries:
        page_total = 0
        for page in range(MAX_PAGES):
            try:
                data = search(q, page=page)
            except Exception as e:
                print(f"[bunjang] '{q}' p{page} 실패: {e} (백오프)")
                time.sleep(3)
                break
            items = data.get("list", [])
            if not items:
                break
            for it in items:
                f = extract_fields(it.get("name", ""))
                price = it.get("price")
                try:
                    price = float(price) if price not in (None, "") else None
                except (TypeError, ValueError):
                    price = None
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "bunjang",
                        str(it.get("pid")),
                        f["title"], f["character"], f["genre"], f["maker"], f["line"],
                        f["scale"], f["condition"],
                        price, "KRW", price,
                        0,                      # 중고 호가
                        f["is_noise"],
                        it.get("location") or "번개장터",
                        str(it.get("category_id") or ""),
                        f"https://m.bunjang.co.kr/products/{it.get('pid')}",
                        it.get("product_image"),
                        _iso(it.get("update_time")),
                        q,
                        now,
                    ),
                )
                page_total += 1
            conn.commit()
            time.sleep(REQUEST_DELAY)
        print(f"[bunjang] '{q}' -> {page_total} rows")
        total += page_total

    conn.close()
    print(f"[bunjang] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
