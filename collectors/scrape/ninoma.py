"""Ninoma(ninoma.com) 수집기 — 필리핀 새제품 호가(PHP).

필리핀 정품 일본 피규어몰(Shopify). Bandai Movie Monster Series·이치방쿠지·
S.H.Figuarts 등 — vendor 메이커 깔끔(Bandai 등), SKU=JAN바코드. 동남아 리테일 호가 표본.
평범한 requests(CF/인증 불필요). 통화 PHP → price_krw fx보정(fx에 PHP 추가됨).

기술 (Shopify 표준 JSON, 2단계 — solaris/cmdstore와 동형):
  1) 검색: `/search/suggest.json?q=<kw>&resources[type]=product&resources[limit]=10`
  2) 상세: `/products/<handle>.json` → vendor(=메이커 깔끔)·product_type·variants[].
  피규어만(product_type == "Figure"; Model Kits/Plush/Board Game 제외). condition new(리테일 새제품).
  variant id를 source_item_id로. is_sold=0(매장 호가).

  python run.py ninoma
"""
import datetime
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://ninoma.com"
SUGGEST = BASE + "/search/suggest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "en;q=0.9"}

# 영문 키워드 (몰이 영문) — 괴수/특촬 라인 + 일본 메이커 라인.
QUERIES = [
    "godzilla", "shin godzilla", "mechagodzilla", "king ghidorah", "movie monster series",
    "ultraman", "ultraman figuarts", "kamen rider", "gridman", "kaiju no 8",
    "gamera", "evangelion", "ichiban kuji", "s.h.figuarts", "s.h.monsterarts",
    "banpresto", "bandai figure", "dinosaur",
]
SUGGEST_LIMIT = 10        # Shopify 하드캡
REQUEST_DELAY = 0.4


def suggest(query):
    params = {"q": query, "resources[type]": "product",
              "resources[limit]": SUGGEST_LIMIT}
    r = requests.get(SUGGEST, headers=HEADERS, params=params, timeout=25)
    r.raise_for_status()
    return (r.json().get("resources", {}).get("results", {}).get("products", []))


def detail(handle):
    url = f"{BASE}/products/{handle}.json"
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.json().get("product")


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='PHP' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    rate = float(row[0]) if row else None
    if rate is None:
        print("[ninoma] 경고: PHP 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    # 1) 검색으로 handle 수집 (쿼리 간 dedup)
    handles = {}
    for q in queries:
        try:
            prods = suggest(q)
        except Exception as e:
            print(f"[ninoma] suggest '{q}' 실패: {e}")
            time.sleep(2)
            continue
        n = 0
        for p in prods:
            h = p.get("handle")
            if h and h not in handles:
                handles[h] = q
                n += 1
        print(f"[ninoma] suggest '{q}' -> {len(prods)}건 ({n} 신규 handle)")
        time.sleep(REQUEST_DELAY)

    # 2) 상세 fetch → variant별 적재
    total = 0
    for h, q in handles.items():
        try:
            d = detail(h)
        except Exception as e:
            print(f"[ninoma] detail '{h}' 실패: {e}")
            time.sleep(1)
            continue
        if not d:
            continue
        ptype = (d.get("product_type") or "").strip().lower()
        if ptype != "figure":        # Model Kits/Plush/Board Game 제외
            continue
        title = d.get("title") or ""
        maker = d.get("vendor")
        url = f"{BASE}/products/{h}"
        imgs = d.get("images") or []
        img = imgs[0].get("src") if (imgs and isinstance(imgs[0], dict)) else None
        f = extract_fields(title)
        for v in (d.get("variants") or []):
            try:
                php = float(v.get("price")) if v.get("price") else None
            except (TypeError, ValueError):
                php = None
            if not php:
                continue
            price_krw = round(php * rate) if (php and rate) else None
            conn.execute(
                """INSERT OR IGNORE INTO product_listing
                   (source, source_item_id, title_raw, character, genre, maker, line,
                    scale, condition, price, currency, price_krw, is_sold, is_noise,
                    mall_name, category, url, image_url, source_date, query, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "ninoma",
                    str(v.get("id")),
                    f["title"], f["character"], f["genre"],
                    maker or f["maker"], f["line"],
                    f["scale"], "new",          # 리테일 새제품
                    php, "PHP", price_krw,
                    0,                          # 매장 호가
                    f["is_noise"],
                    "Ninoma",
                    d.get("product_type"),
                    url, img,
                    None,                       # 발매일 없음
                    q,
                    now,
                ),
            )
            total += 1
        conn.commit()
        time.sleep(REQUEST_DELAY)

    conn.close()
    print(f"[ninoma] done. total {total} rows ({len(handles)} products) @ {now}")


if __name__ == "__main__":
    collect()
