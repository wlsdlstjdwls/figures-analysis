"""Solaris Japan 수집기 — 일본 피규어 **새제품 정가 + 중고 호가**(USD).

일본 피규어 영문몰(Shopify). 한 상품에 **Brand New / Pre Owned 두 변형(variant)** →
일본 새제품 정가와 일본 중고 호가를 **한 소스에서 동시** 확보. amiami(새)·suruga/yahoo(중고) 보완.
평범한 requests(CF/인증 불필요). 통화 USD → price_krw fx보정.

기술 (Shopify 표준 JSON, 2단계):
  1) 검색: `/search/suggest.json?q=<kw>&resources[type]=product&resources[limit]=10`
     → results.products[] (handle·title·type·tags·image·url·price범위). ⚠️ limit 10 하드캡.
  2) 상세: `/products/<handle>.json` → product.vendor(메이커)·product_type·variants[]
     각 variant: option1("Brand New"/"Pre Owned")·price(USD)·sku·id.
  피규어만(`product_type=="Figure"` 또는 tags에 `meta-figure-`). DVD/Book/Apparel 등 제외.
  variant id를 source_item_id로 → 새/중고 행이 별개로 적재. is_sold=0(매장 호가).

  python run.py solaris
"""
import datetime
import time
import urllib.parse as up

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.solarisjapan.com"
SUGGEST = BASE + "/search/suggest.json"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "application/json", "Accept-Language": "en;q=0.9"}

# 영문 키워드 (몰이 영문) — 괴수/특촬/공룡 라인. hlj/bbts QUERIES와 동계열.
QUERIES = [
    "godzilla", "godzilla sofubi", "shin godzilla", "mechagodzilla", "king ghidorah",
    "x-plus godzilla", "s.h.monsterarts godzilla", "movie monster series",
    "ultraman", "ultraman sofubi", "ultraman taro", "ultraman tiga",
    "kamen rider", "kamen rider sofubi", "gridman", "kaiju no 8",
    "kaiju sofubi", "dinosaur sofubi", "gamera", "evangelion",
]
SUGGEST_LIMIT = 10        # Shopify 하드캡
REQUEST_DELAY = 0.5

# 비피규어 제외 (product_type 값이 가게마다 다름 → meta-figure 태그도 병행 확인)
SKIP_TYPES = {"video", "dvd", "blu-ray", "book", "manga", "cd", "apparel",
              "t-shirt", "poster", "trading card", "game", "soundtrack", "artbook"}


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


def _is_figure(ptype, tags):
    if ptype and ptype.strip().lower() in SKIP_TYPES:
        return False
    if ptype and ptype.strip().lower() == "figure":
        return True
    return any(isinstance(t, str) and t.startswith("meta-figure-") for t in (tags or []))


def _condition(opt):
    o = (opt or "").strip().lower()
    if "pre owned" in o or "pre-owned" in o or "used" in o:
        return "used"
    return "new"          # "Brand New" 및 단일 variant 기본


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='USD' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    rate = float(row[0]) if row else None
    if rate is None:
        print("[solaris] 경고: USD 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")

    # 1) 검색으로 handle 수집 (쿼리 간 dedup)
    handles = {}
    for q in queries:
        try:
            prods = suggest(q)
        except Exception as e:
            print(f"[solaris] suggest '{q}' 실패: {e}")
            time.sleep(2)
            continue
        n = 0
        for p in prods:
            h = p.get("handle")
            if h and h not in handles:
                handles[h] = q
                n += 1
        print(f"[solaris] suggest '{q}' -> {len(prods)}건 ({n} 신규 handle)")
        time.sleep(REQUEST_DELAY)

    # 2) 상세 fetch → variant별(새/중고) 적재
    total = 0
    for h, q in handles.items():
        try:
            d = detail(h)
        except Exception as e:
            print(f"[solaris] detail '{h}' 실패: {e}")
            time.sleep(1)
            continue
        if not d:
            continue
        if not _is_figure(d.get("product_type"), d.get("tags")):
            continue
        title = d.get("title") or ""
        vendor = d.get("vendor")
        url = f"{BASE}/products/{h}"
        img = None
        imgs = d.get("images") or []
        if imgs:
            img = imgs[0].get("src") if isinstance(imgs[0], dict) else None
        f = extract_fields(title)
        for v in (d.get("variants") or []):
            try:
                usd = float(v.get("price")) if v.get("price") else None
            except (TypeError, ValueError):
                usd = None
            if not usd:
                continue
            cond = _condition(v.get("option1"))
            price_krw = round(usd * rate) if (usd and rate) else None
            conn.execute(
                """INSERT OR IGNORE INTO product_listing
                   (source, source_item_id, title_raw, character, genre, maker, line,
                    scale, condition, price, currency, price_krw, is_sold, is_noise,
                    mall_name, category, url, image_url, source_date, query, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "solaris",
                    str(v.get("id")),
                    f["title"], f["character"], f["genre"],
                    vendor or f["maker"], f["line"],
                    f["scale"], cond,
                    usd, "USD", price_krw,
                    0,                          # 매장 호가
                    f["is_noise"],
                    "Solaris Japan",
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
    print(f"[solaris] done. total {total} rows ({len(handles)} products) @ {now}")


if __name__ == "__main__":
    collect()
