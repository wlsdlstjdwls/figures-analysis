"""CMD Store(cmdstore.com) 수집기 — 미국 새제품 정가(USD).

미국 토이몰(Shopify). 괴수/특촬 액션피규어 풍부 — S.H.MonsterArts·Figuarts·
Movie Monster Series·Hiya·Funko 등. BBTS/EE/Toynk 보완.
평범한 requests(CF/인증 불필요). 통화 USD → price_krw fx보정.

기술 (Shopify 표준 JSON, 2단계 — solaris와 동형):
  1) 검색: `/search/suggest.json?q=<kw>&resources[type]=product&resources[limit]=10`
     → results.products[] (handle·title·type·vendor·price·image). ⚠️ limit 10 하드캡.
  2) 상세: `/products/<handle>.json` → product_type·variants[]·images.
     ⚠️ vendor 필드는 **콤마조인 태그열**("Movie,...,Hiya Toys") → 메이커 = 마지막 세그먼트.
  피규어만(product_type에 "figure" 포함: Action/Statue/Static Figure). 미국몰 = condition new 고정.
  variant id를 source_item_id로. is_sold=0(매장 호가).

  python run.py cmdstore
"""
import datetime
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.cmdstore.com"
SUGGEST = BASE + "/search/suggest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "en;q=0.9"}

# 영문 키워드 — 괴수/특촬/공룡 라인 (solaris/hlj와 동계열).
QUERIES = [
    "godzilla", "shin godzilla", "mechagodzilla", "king ghidorah", "godzilla minus one",
    "monsterverse", "s.h.monsterarts", "movie monster series", "x-plus",
    "ultraman", "ultraman figuarts", "ultraman taro", "ultraman tiga", "ultraman arc",
    "kamen rider", "kamen rider figuarts", "gridman", "kaiju no 8",
    "gamera", "evangelion", "hiya toys", "dinosaur",
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


def _is_figure(ptype):
    return bool(ptype) and "figure" in ptype.strip().lower()


def _maker(vendor):
    """vendor = 콤마조인 태그열 → 마지막 세그먼트가 실제 메이커(Hiya Toys/Bandai/Tamashii Nations)."""
    if not vendor:
        return None
    parts = [p.strip() for p in vendor.split(",") if p.strip()]
    return parts[-1] if parts else None


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='USD' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    rate = float(row[0]) if row else None
    if rate is None:
        print("[cmdstore] 경고: USD 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    # 1) 검색으로 handle 수집 (쿼리 간 dedup)
    handles = {}
    for q in queries:
        try:
            prods = suggest(q)
        except Exception as e:
            print(f"[cmdstore] suggest '{q}' 실패: {e}")
            time.sleep(2)
            continue
        n = 0
        for p in prods:
            h = p.get("handle")
            if h and h not in handles:
                handles[h] = q
                n += 1
        print(f"[cmdstore] suggest '{q}' -> {len(prods)}건 ({n} 신규 handle)")
        time.sleep(REQUEST_DELAY)

    # 2) 상세 fetch → variant별 적재
    total = 0
    for h, q in handles.items():
        try:
            d = detail(h)
        except Exception as e:
            print(f"[cmdstore] detail '{h}' 실패: {e}")
            time.sleep(1)
            continue
        if not d:
            continue
        if not _is_figure(d.get("product_type")):
            continue
        title = d.get("title") or ""
        maker = _maker(d.get("vendor"))
        url = f"{BASE}/products/{h}"
        imgs = d.get("images") or []
        img = imgs[0].get("src") if (imgs and isinstance(imgs[0], dict)) else None
        f = extract_fields(title)
        for v in (d.get("variants") or []):
            try:
                usd = float(v.get("price")) if v.get("price") else None
            except (TypeError, ValueError):
                usd = None
            if not usd:
                continue
            price_krw = round(usd * rate) if (usd and rate) else None
            conn.execute(
                """INSERT OR IGNORE INTO product_listing
                   (source, source_item_id, title_raw, character, genre, maker, line,
                    scale, condition, price, currency, price_krw, is_sold, is_noise,
                    mall_name, category, url, image_url, source_date, query, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "cmdstore",
                    str(v.get("id")),
                    f["title"], f["character"], f["genre"],
                    maker or f["maker"], f["line"],
                    f["scale"], "new",          # 미국몰 = 새제품
                    usd, "USD", price_krw,
                    0,                          # 매장 호가
                    f["is_noise"],
                    "CMD Store",
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
    print(f"[cmdstore] done. total {total} rows ({len(handles)} products) @ {now}")


if __name__ == "__main__":
    collect()
