"""Toynk 수집기 — 미국 새제품 **정가**(USD).

미국 토이몰(Shopify). monsterverse(고질라x콩)·맥팔레인·반다이 등 새제품 정가.
BBTS/Entertainment Earth 보완(미국 시세 표본↑). 평범한 requests. USD → price_krw fx보정.

기술 (Shopify 표준 JSON, 2단계 — solaris.py와 동형):
  1) `/search/suggest.json?q=<kw>&resources[type]=product&resources[limit]=10` (10 하드캡)
  2) `/products/<handle>.json` → vendor(메이커)·product_type·variants[].price(USD)
  미국몰이라 중고 없음 → condition=new 고정, is_sold=0(매장 호가).

  python run.py toynk
"""
import datetime
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://toynk.com"
SUGGEST = BASE + "/search/suggest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "en;q=0.9"}

# 영문 키워드 (bbts/entearth와 동계열, 미국몰 취급 라인 위주)
QUERIES = [
    "godzilla", "godzilla vs kong", "monsterverse", "mechagodzilla", "king ghidorah",
    "ultraman", "kamen rider", "kaiju no 8", "jurassic", "dinosaur figure",
    "s.h.monsterarts", "neca godzilla", "mcfarlane dinosaur", "bandai godzilla",
]
SUGGEST_LIMIT = 10
REQUEST_DELAY = 0.5


def suggest(query):
    params = {"q": query, "resources[type]": "product",
              "resources[limit]": SUGGEST_LIMIT}
    r = requests.get(SUGGEST, headers=HEADERS, params=params, timeout=25)
    r.raise_for_status()
    return r.json().get("resources", {}).get("results", {}).get("products", [])


def detail(handle):
    r = requests.get(f"{BASE}/products/{handle}.json", headers=HEADERS, timeout=25)
    r.raise_for_status()
    return r.json().get("product")


def _is_figure(ptype, tags):
    t = (ptype or "").lower()
    if "figure" in t or "statue" in t or "model kit" in t:
        return True
    return any(isinstance(x, str) and x.startswith("meta-figure-") for x in (tags or []))


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='USD' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    rate = float(row[0]) if row else None
    if rate is None:
        print("[toynk] 경고: USD 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    handles = {}
    for q in queries:
        try:
            prods = suggest(q)
        except Exception as e:
            print(f"[toynk] suggest '{q}' 실패: {e}")
            time.sleep(2)
            continue
        new = 0
        for p in prods:
            h = p.get("handle")
            if h and h not in handles:
                handles[h] = q
                new += 1
        print(f"[toynk] suggest '{q}' -> {len(prods)}건 ({new} 신규 handle)")
        time.sleep(REQUEST_DELAY)

    total = 0
    for h, q in handles.items():
        try:
            d = detail(h)
        except Exception as e:
            print(f"[toynk] detail '{h}' 실패: {e}")
            time.sleep(1)
            continue
        if not d or not _is_figure(d.get("product_type"), d.get("tags")):
            continue
        title = d.get("title") or ""
        vendor = d.get("vendor")
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
                    "toynk", str(v.get("id")),
                    f["title"], f["character"], f["genre"],
                    vendor or f["maker"], f["line"], f["scale"], "new",
                    usd, "USD", price_krw,
                    0, f["is_noise"], "Toynk", d.get("product_type"),
                    f"{BASE}/products/{h}", img, None, q, now,
                ),
            )
            total += 1
        conn.commit()
        time.sleep(REQUEST_DELAY)

    conn.close()
    print(f"[toynk] done. total {total} rows ({len(handles)} products) @ {now}")


if __name__ == "__main__":
    collect()
