"""Galactic Toys(galactictoys.com) 수집기 — 미국 새제품 정가(USD).

미국 토이몰(Shopify). ⭐ 괴수/특촬 피규어 매우 풍부 — Ichibansho·S.H.MonsterArts·
Movie Monster Series·Tamashii Nations·Hiya. BBTS/EE/CMD/Toynk 보완.
평범한 requests(CF/인증 불필요). 통화 USD → price_krw fx보정.

기술 (Shopify 표준 JSON, 2단계 — cmdstore/solaris와 동형):
  1) 검색: `/search/suggest.json` → results.products[] (handle). limit 10 하드캡.
  2) 상세: `/products/<handle>.json` → product_type·variants[]·vendor(=메이커, 단일 깔끔).
  피규어만: product_type ∈ {Figures, Character Models, Plush Figure, Mecha Girl Models}
  또는 "figure" 포함. ⚠️ 노이즈 제외: Labubu(블박)·Warhammer·Mecha Models(건프라)·
  Card Accessories·Hobby Supplies. 미국몰 = condition new 고정. variant id = source_item_id.

  python run.py galactictoys
"""
import datetime
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://galactictoys.com"
SUGGEST = BASE + "/search/suggest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "en;q=0.9"}

QUERIES = [
    "godzilla", "shin godzilla", "mechagodzilla", "king ghidorah", "godzilla minus one",
    "monsterverse", "s.h.monsterarts", "movie monster series", "ichibansho", "x-plus",
    "ultraman", "ultraman figuarts", "ultraman taro", "ultraman tiga", "ultraman arc",
    "kamen rider", "kamen rider figuarts", "gridman", "kaiju no 8",
    "gamera", "evangelion", "dinosaur",
]
SUGGEST_LIMIT = 10
REQUEST_DELAY = 0.4

# product_type 화이트리스트(소문자). 외 + "figure" 포함이면 통과.
FIG_TYPES = {"figures", "character models", "plush figure", "mecha girl models"}


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
    if not ptype:
        return False
    t = ptype.strip().lower()
    return t in FIG_TYPES or "figure" in t


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='USD' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    rate = float(row[0]) if row else None
    if rate is None:
        print("[galactictoys] 경고: USD 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    handles = {}
    for q in queries:
        try:
            prods = suggest(q)
        except Exception as e:
            print(f"[galactictoys] suggest '{q}' 실패: {e}")
            time.sleep(2)
            continue
        n = 0
        for p in prods:
            h = p.get("handle")
            if h and h not in handles:
                handles[h] = q
                n += 1
        print(f"[galactictoys] suggest '{q}' -> {len(prods)}건 ({n} 신규 handle)")
        time.sleep(REQUEST_DELAY)

    total = 0
    for h, q in handles.items():
        try:
            d = detail(h)
        except Exception as e:
            print(f"[galactictoys] detail '{h}' 실패: {e}")
            time.sleep(1)
            continue
        if not d:
            continue
        if not _is_figure(d.get("product_type")):
            continue
        title = d.get("title") or ""
        vendor = (d.get("vendor") or "").strip() or None
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
                    "galactictoys",
                    str(v.get("id")),
                    f["title"], f["character"], f["genre"],
                    vendor or f["maker"], f["line"],
                    f["scale"], "new",
                    usd, "USD", price_krw,
                    0,
                    f["is_noise"],
                    "Galactic Toys",
                    d.get("product_type"),
                    url, img,
                    None,
                    q,
                    now,
                ),
            )
            total += 1
        conn.commit()
        time.sleep(REQUEST_DELAY)

    conn.close()
    print(f"[galactictoys] done. total {total} rows ({len(handles)} products) @ {now}")


if __name__ == "__main__":
    collect()
