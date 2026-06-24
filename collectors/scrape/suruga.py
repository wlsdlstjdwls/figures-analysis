"""스루가야(Suruga-ya) 수집기 — 일본 중고/재고 **정찰가**(고정가 매장).

야후옥션(낙찰=실거래)과 달리 스루가야는 매입·판매 고정가 매장 → "일본 중고 호가/정찰가".
yahoo_jp 실거래 보완 + 매입원가 밴드 표본.

⚠️ Cloudflare managed challenge("しばらくお待ちください")가 강해 평범 requests/headless Playwright
   (stealth·headed 포함) 모두 미통과. → **FlareSolverr**(도커 `ghcr.io/flaresolverr/flaresolverr`,
   포트 8191) 경유로 CF 해결. `docker run -d --name flaresolverr -p 8191:8191 ...`.

파싱: 검색결과 각 카드는 `<div class="photo_box">`로 시작 → product/detail/<id> + h3.product-name(풀제목)
      + .condition(상품타입) + .brand(메이커 JP). 가격은 페이지 내 GTM JS `item_product.price`(정수 JPY)
      를 item_id로 매핑(DOM 가격표기는 배송표/타임세일 섞여 지저분).

  python run.py suruga      # (사전: FlareSolverr 도커 실행)
"""
import datetime
import html as _html
import os
import re
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.suruga-ya.jp"
FLARESOLVERR = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")

# yahoo_jp 라인과 정렬 (KEEP IN SYNC: yahoo_jp.py QUERIES)
QUERIES = [
    "ゴジラ ソフビ", "ウルトラマン ソフビ", "仮面ライダー ソフビ", "怪獣 ソフビ",
    "ムービーモンスター ゴジラ", "一番くじ ゴジラ", "X-PLUS ゴジラ",
    "ダイナゼノン", "グリッドマン", "怪獣8号",
]
MAX_PAGES = 2          # query당 (FlareSolverr 1회 solve가 느려 보수적)
SOLVE_TIMEOUT = 90000  # ms

_JS_PRICE_RE = re.compile(
    r"item_id:\s*common\.htmlDecode\(.(\d+).\).*?price:\s*(\d+)", re.S)
_ID_RE = re.compile(r"/product/detail/(\d+)")
_TITLE_RE = re.compile(r'product-name">(.*?)</h3>', re.S)
_COND_RE = re.compile(r'class="condition[^>]*>(.*?)</p>', re.S)
_BRAND_RE = re.compile(r'class="brand">\[?(.*?)\]?\s*</p>', re.S)
_REL_RE = re.compile(r"発売日：([0-9/]+)")


def _jpy_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='JPY' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def _solve(sess, url):
    """FlareSolverr로 CF 해결 후 HTML 반환(없으면 None)."""
    r = sess.post(FLARESOLVERR, json={"cmd": "request.get", "url": url,
                                      "maxTimeout": SOLVE_TIMEOUT}, timeout=130)
    r.raise_for_status()
    d = r.json()
    if d.get("status") != "ok":
        return None
    return d.get("solution", {}).get("response")


def _parse(html):
    """검색 HTML → [dict] (id,title,price,cond,brand,rel,soldout)."""
    prices = {m.group(1): int(m.group(2)) for m in _JS_PRICE_RE.finditer(html)}
    rows = []
    for card in html.split('<div class="photo_box')[1:]:
        mid = _ID_RE.search(card)
        mt = _TITLE_RE.search(card)
        if not (mid and mt):
            continue
        iid = mid.group(1)
        title = _html.unescape(re.sub(r"<[^>]+>", "", mt.group(1))).strip()
        mc = _COND_RE.search(card)
        mb = _BRAND_RE.search(card)
        mr = _REL_RE.search(card)
        rows.append({
            "id": iid,
            "title": title,
            "price": prices.get(iid),
            "cond": re.sub(r"<[^>]+>", "", mc.group(1)).strip() if mc else None,
            "brand": mb.group(1).strip() if mb else None,
            "rel": mr.group(1) if mr else None,
            "soldout": bool(re.search(r"品切れ|売切", card)),
        })
    return rows


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _jpy_rate(conn)
    if rate is None:
        print("[suruga] 경고: JPY 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    sess = requests.Session()
    # FlareSolverr 헬스체크
    try:
        sess.get(FLARESOLVERR.replace("/v1", "/"), timeout=10)
    except Exception:
        print(f"[suruga] FlareSolverr({FLARESOLVERR}) 응답없음. 도커 컨테이너 실행 필요 → 중단.")
        conn.close()
        return
    total = 0

    for q in queries:
        q_total = 0
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/search?search_word={q}&page={page}"
            try:
                html = _solve(sess, url)
            except Exception as e:
                print(f"[suruga] '{q}' p{page} solve 실패: {e}")
                time.sleep(2)
                break
            if not html:
                break
            rows = _parse(html)
            if not rows:
                break
            for r in rows:
                jpy = float(r["price"]) if r["price"] else None
                price_krw = round(jpy * rate) if (jpy and rate) else None
                f = extract_fields(r["title"])
                cat = r["cond"] or ""
                if r["soldout"]:
                    cat = ("품절/" + cat).strip("/")
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "suruga",
                        r["id"],
                        f["title"], f["character"], f["genre"],
                        r["brand"] or f["maker"], f["line"],
                        f["scale"], "used",            # 스루가야=중고 정찰가 위주
                        jpy, "JPY", price_krw,
                        0,                              # 매장 고정가(호가 성격), 낙찰 아님
                        f["is_noise"],
                        "駿河屋",
                        cat,
                        f"{BASE}/product/detail/{r['id']}",
                        f"{BASE}/database/photo.php?shinaban={r['id']}&size=m",
                        r["rel"],
                        q,
                        now,
                    ),
                )
                q_total += 1
            conn.commit()
            time.sleep(1.0)
        print(f"[suruga] '{q}' -> {q_total} rows")
        total += q_total

    conn.close()
    print(f"[suruga] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
