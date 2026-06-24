r"""Hobby Search(1999.co.jp) 수집기 — 일본(영문몰) 새제품 **정가**(JPY).

HLJ/amiami와 같은 일본 하비 리테일러. 정가 표본↑.
⚠️ 전사 Cloudflare("Just a moment") → **FlareSolverr**(도커 8191) 경유. suruga와 동일 인프라.

기술: `/eng/search?searchkey=<kw>&cat=figure&typ1_c=` (검색 param은 searchkey, cat=figure로 피규어 한정).
  결과 카드 `c-card`:
   - itemcode `itemcode="(\d+)"` / 링크 `/eng/<itemcode>`
   - 이름 `c-card__title">...</div>`
   - 정가(스트리트) `c-card__price-element"><span>5,354</span> JPY`
   - 발매일 `c-card__maker">Late Jul., 2022 Released</div>`
   - 이미지 `/itbigNN/<code>.jpg`

  python run.py hobbysearch   # (사전: FlareSolverr 도커 실행)
"""
import datetime
import html as _html
import os
import re
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.1999.co.jp"
FLARESOLVERR = os.environ.get("FLARESOLVERR_URL", "http://localhost:8191/v1")

# 영문몰이라 영어 키워드 (괴수/특촬 도메인)
QUERIES = [
    "godzilla", "ultraman", "kamen rider", "kaiju sofubi", "gamera",
    "gridman", "dynazenon", "kaiju no.8", "x-plus godzilla",
]
MAX_PAGES = 2          # query당 (FlareSolverr solve 느려 보수적)
SOLVE_TIMEOUT = 90000  # ms

_CARD_RE = re.compile(r'<div class="c-card">(.*?)(?=<div class="c-card">|<div class="c-product-index__pagination)', re.S)
_CODE_RE = re.compile(r'itemcode="(\d+)"')
_TITLE_RE = re.compile(r'c-card__title">(.*?)</div>', re.S)
_PRICE_RE = re.compile(r'c-card__price-element"><span[^>]*>([\d,]+)</span>\s*JPY', re.S)
_REL_RE = re.compile(r'c-card__maker">(.*?)</div>', re.S)
_IMG_RE = re.compile(r'<img src="(/itbig\d+/\d+\.jpg)"')


def _jpy_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='JPY' ORDER BY date DESC LIMIT 1"
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


def _clean(s):
    return _html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _parse(html):
    html = re.sub(r"<svg.*?</svg>", "", html, flags=re.S)
    rows = []
    for block in _CARD_RE.findall(html):
        mc = _CODE_RE.search(block)
        mt = _TITLE_RE.search(block)
        if not (mc and mt):
            continue
        mp = _PRICE_RE.search(block)
        mr = _REL_RE.search(block)
        mi = _IMG_RE.search(block)
        rows.append({
            "id": mc.group(1),
            "title": _clean(mt.group(1)),
            "price": float(mp.group(1).replace(",", "")) if mp else None,
            "rel": _clean(mr.group(1)) if mr else None,
            "image": (BASE + mi.group(1)) if mi else None,
        })
    return rows


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _jpy_rate(conn)
    if rate is None:
        print("[hobbysearch] 경고: JPY 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    sess = requests.Session()
    try:
        sess.get(FLARESOLVERR.replace("/v1", "/"), timeout=10)
    except Exception:
        print(f"[hobbysearch] FlareSolverr({FLARESOLVERR}) 응답없음. 도커 실행 필요 → 중단.")
        conn.close()
        return
    total = 0

    for q in queries:
        q_total = 0
        for page in range(1, MAX_PAGES + 1):
            url = f"{BASE}/eng/search?searchkey={q}&cat=figure&typ1_c=&page={page}"
            try:
                html = _solve(sess, url)
            except Exception as e:
                print(f"[hobbysearch] '{q}' p{page} solve 실패: {e}")
                time.sleep(2)
                break
            if not html:
                break
            rows = _parse(html)
            if not rows:
                break
            for r in rows:
                jpy = r["price"]
                price_krw = round(jpy * rate) if (jpy and rate) else None
                f = extract_fields(r["title"])
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "hobbysearch",
                        r["id"],
                        f["title"], f["character"], f["genre"], f["maker"], f["line"],
                        f["scale"], "new",
                        jpy, "JPY", price_krw,
                        0,                          # 정가
                        f["is_noise"],
                        "HobbySearch",
                        None,
                        f"{BASE}/eng/{r['id']}",
                        r["image"],
                        r["rel"],                   # 발매(예정)일 문자열
                        q,
                        now,
                    ),
                )
                q_total += 1
            conn.commit()
            time.sleep(1.0)
        print(f"[hobbysearch] '{q}' -> {q_total} rows")
        total += q_total

    conn.close()
    print(f"[hobbysearch] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
