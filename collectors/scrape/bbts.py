"""BBTS(BigBadToyStore) 수집기 — 해외(미국) **새제품 정가**(USD).

HLJ의 미국판. 해외 정가 표본 보강 + 미국 출시 라인(NECA·Super7·Hiya 등) 커버.
Cloudflare challenge(Cf-Mitigated)로 평범한 requests 403 → amiami처럼 Playwright로 로드.
검색결과는 서버렌더 DOM(`.product-card`) → 페이지 컨텍스트에서 카드 파싱(XHR API 없음).

카드 필드: href(/product/...-<code>?variation=), title, company("By: <maker>"),
           price("PRE-ORDER\\n$129.99" 식 — 상태+USD), img.
통화 USD → price_krw fx 보정. condition new, is_sold 0(소매 정가/호가).

  python run.py bbts
"""
import datetime
import re

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://www.bigbadtoystore.com"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121 Safari/537.36")

# amiami/hlj 라인과 정렬 (KEEP IN SYNC). BBTS는 영어 일반명이라 sofubi 등 제거.
QUERIES = [
    "godzilla", "ultraman", "gamera", "kamen rider",
    "kaiju", "gridman", "dynazenon", "kaiju no.8",
]
MAX_PAGES = 3          # query당 최대 60건 (20/page)
PRICE_RE = re.compile(r"\$([0-9,]+\.[0-9]{2})")
CODE_RE = re.compile(r"-(\d+)(?:\?|$)")

# 카드 파싱 JS (페이지 컨텍스트)
_CARD_JS = """() => {
  const out=[];
  document.querySelectorAll('.product-card').forEach(c=>{
    const a=c.closest('a')||c.querySelector('a')||(c.parentElement&&c.parentElement.closest('a'));
    out.push({
      href: a? a.getAttribute('href'): null,
      title: (c.querySelector('.product-card-title')||{}).textContent||'',
      company: (c.querySelector('.product-company')||{}).textContent||'',
      price: (c.querySelector('.product-card-pricing')||{}).textContent||'',
      img: (c.querySelector('img')||{}).src||'',
    });
  });
  return out;
}"""


def _usd_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='USD' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def _parse(row):
    """카드 dict → 정규화된 값. (code, title, maker, usd, status, url, img) or None."""
    href = (row.get("href") or "").strip()
    if not href:
        return None
    m = CODE_RE.search(href.split("?")[0])
    code = m.group(1) if m else href.rsplit("-", 1)[-1].split("?")[0]
    title = (row.get("title") or "").strip()
    maker = (row.get("company") or "").replace("By:", "").strip() or None
    ptxt = (row.get("price") or "").strip()
    pm = PRICE_RE.search(ptxt)
    usd = float(pm.group(1).replace(",", "")) if pm else None
    status = ptxt.split("\n")[0].strip()[:30] if ptxt else None   # PRE-ORDER / IN STOCK ...
    url = (BASE + href) if href.startswith("/") else href
    return code, title, maker, usd, status, url, (row.get("img") or "").strip() or None


def collect(queries=None):
    from playwright.sync_api import sync_playwright

    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _usd_rate(conn)
    if rate is None:
        print("[bbts] 경고: USD 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    with sync_playwright() as p:
        b = p.chromium.launch()

        for q in queries:
            q_total = 0
            # 쿼리마다 fresh context (CF 피로 회피 — 한 컨텍스트로 다량 탐색 시 차단됨)
            ctx = b.new_context(user_agent=UA)
            pg = ctx.new_page()
            for page in range(1, MAX_PAGES + 1):
                try:
                    pg.goto(f"{BASE}/Search?SearchText={q}&Page={page}",
                            wait_until="domcontentloaded", timeout=60000)
                    # CF managed challenge 자동해제까지 폴링(.product-card 등장 대기)
                    rows = []
                    for _ in range(15):
                        rows = pg.evaluate(_CARD_JS)
                        if rows:
                            break
                        pg.wait_for_timeout(1000)
                except Exception as e:
                    print(f"[bbts] '{q}' p{page} 실패: {str(e).splitlines()[0]}")
                    pg.wait_for_timeout(1500)
                    break
                if not rows:
                    break
                for row in rows:
                    parsed = _parse(row)
                    if not parsed:
                        continue
                    code, title, maker, usd, status, url, img = parsed
                    price_krw = round(usd * rate) if (usd and rate) else None
                    f = extract_fields(title)
                    conn.execute(
                        """INSERT OR IGNORE INTO product_listing
                           (source, source_item_id, title_raw, character, genre, maker, line,
                            scale, condition, price, currency, price_krw, is_sold, is_noise,
                            mall_name, category, url, image_url, query, collected_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "bbts",
                            code,
                            f["title"], f["character"], f["genre"],
                            maker or f["maker"], f["line"],
                            f["scale"], "new",
                            usd, "USD", price_krw,
                            0,                          # 소매 정가/호가
                            f["is_noise"],
                            "BBTS",
                            status,                     # PRE-ORDER / IN STOCK
                            url,
                            img,
                            q,
                            now,
                        ),
                    )
                    q_total += 1
                conn.commit()
            print(f"[bbts] '{q}' -> {q_total} rows")
            total += q_total
            ctx.close()

        b.close()

    conn.close()
    print(f"[bbts] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
