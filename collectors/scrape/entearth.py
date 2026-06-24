"""Entertainment Earth 수집기 — 미국 새제품 **정가**(USD).

BBTS와 같은 미국 리테일러. 미국 정가 표본↑.
⚠️ 전사 Cloudflare("Just a moment") → **FlareSolverr**(도커 8191) 경유. suruga와 동일 인프라.

기술: `/s/?query1=<kw>` (검색 param은 query1). 결과 카드 `.product product-hover` 안의
  `<button class="btn add-to-cart" data-*>`에 구조화 데이터:
   - data-sku(고유 id) · data-price(USD) · data-name · data-company(메이커) ·
     data-theme · data-character · data-collect(카테고리)
  링크 `product-url product-link" href="/product/.../<sku>"`, 이미지 media.entertainmentearth.com.

  python run.py entearth   # (사전: FlareSolverr 도커 실행)
"""
import datetime
import html as _html
import os
import re
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.entertainmentearth.com"
FLARESOLVERR = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")

QUERIES = [
    "godzilla", "ultraman", "kaiju", "gamera", "kamen rider",
    "king kong", "jurassic dinosaur", "pacific rim",
]
MAX_PAGES = 2
SOLVE_TIMEOUT = 90000

_BLOCK_RE = re.compile(r'class="product product-hover">(.*?)(?=class="product product-hover">|<nav|<footer)', re.S)
_HREF_RE = re.compile(r'product-url product-link" href="(/product/[^"]+)"')
_CART_RE = re.compile(r'<button class="btn add-to-cart[^"]*"(.*?)>', re.S)
_IMG_RE = re.compile(r'<img src="(https://media\.entertainmentearth\.com/[^"]+)"')


def _attr(s, name):
    m = re.search(rf'data-{name}="([^"]*)"', s)
    return _html.unescape(m.group(1)).strip() if m else None


def _usd_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='USD' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def _solve(sess, url):
    r = sess.post(FLARESOLVERR, json={"cmd": "request.get", "url": url,
                                      "maxTimeout": SOLVE_TIMEOUT}, timeout=130)
    r.raise_for_status()
    d = r.json()
    if d.get("status") != "ok":
        return None
    return d.get("solution", {}).get("response")


def _parse(html):
    html = re.sub(r"<svg.*?</svg>", "", html, flags=re.S)
    rows = []
    for block in _BLOCK_RE.findall(html):
        cm = _CART_RE.search(block)
        if not cm:
            continue
        attrs = cm.group(1)
        sku = _attr(attrs, "sku")
        name = _attr(attrs, "name")
        if not (sku and name):
            continue
        price = _attr(attrs, "price")
        try:
            price = float(price) if price else None
        except ValueError:
            price = None
        hm = _HREF_RE.search(block)
        im = _IMG_RE.search(block)
        rows.append({
            "id": sku,
            "name": name,
            "price": price,
            "maker": _attr(attrs, "company"),
            "category": _attr(attrs, "collect"),
            "url": (BASE + hm.group(1)) if hm else f"{BASE}/p/{sku.lower()}",
            "image": im.group(1) if im else None,
        })
    return rows


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _usd_rate(conn)
    if rate is None:
        print("[entearth] 경고: USD 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    sess = requests.Session()
    try:
        sess.get(FLARESOLVERR.replace("/v1", "/"), timeout=10)
    except Exception:
        print(f"[entearth] FlareSolverr({FLARESOLVERR}) 응답없음. 도커 실행 필요 → 중단.")
        conn.close()
        return
    total = 0

    for q in queries:
        q_total = 0
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/s/?query1={q.replace(' ', '+')}&page={page}"
            try:
                html = _solve(sess, url)
            except Exception as e:
                print(f"[entearth] '{q}' p{page} solve 실패: {e}")
                time.sleep(2)
                break
            if not html:
                break
            rows = _parse(html)
            if not rows:
                break
            for r in rows:
                usd = r["price"]
                price_krw = round(usd * rate) if (usd and rate) else None
                f = extract_fields(r["name"])
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "entearth",
                        r["id"],
                        f["title"], f["character"], f["genre"],
                        r["maker"] or f["maker"], f["line"],
                        f["scale"], "new",
                        usd, "USD", price_krw,
                        0,                          # 정가
                        f["is_noise"],
                        "EntertainmentEarth",
                        r["category"],
                        r["url"],
                        r["image"],
                        None,
                        q,
                        now,
                    ),
                )
                q_total += 1
            conn.commit()
            time.sleep(1.0)
        print(f"[entearth] '{q}' -> {q_total} rows")
        total += q_total

    conn.close()
    print(f"[entearth] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
