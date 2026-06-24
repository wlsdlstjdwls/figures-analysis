"""아미아미(AmiAmi) 수집기 — 일본 새제품 정가 + 발매일 + JAN바코드.

API는 Cloudflare가 TLS핑거프린트로 평범한 requests 차단(403).
→ Playwright 브라우저로 사이트 로드(CF 통과) 후, 페이지 내 fetch로 내부 API 호출.

api.amiami.com/api/v1.0/items?s_keywords=&pagecnt=&pagemax=&lang=eng  (헤더 X-User-Key: amiami_dev)
필드: gcode, gname, min_price(정가 JPY), c_price_taxed, maker_name, releasedate(발매일!),
      jancode(바코드→매칭), thumb_url, salestatus.

가치: 발매일(출시일) + 정가 → 프리미엄율(중고시세/정가) 계산 기반. JAN으로 사이트간 매칭.
새제품 정가는 자주 안 바뀜 → 저빈도 수집(주 1회 등). PLAN §10.6.

  python run.py amiami
"""
import datetime

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

IMG_BASE = "https://img.amiami.com"
QUERIES = [
    "godzilla sofubi", "ultraman sofubi", "kaiju sofubi", "gamera sofubi",
    "kamen rider sofubi", "sofubi", "soft vinyl kaiju",
    # ── 한일 겹침 정렬 (국내 naver/bunjang 라인과 동일 제품 노림, KEEP IN SYNC) ──
    "SSSS.GRIDMAN sofubi", "SSSS.DYNAZENON sofubi", "kaiju no.8 sofubi",
    "movie monster godzilla", "shin godzilla sofubi", "godzilla minus one sofubi",
    "ichiban kuji godzilla", "ichiban kuji kamen rider", "ultra big sofubi",
    "x-plus godzilla",
]
PAGEMAX = 50
MAX_PAGES = 3          # query당 최대 150건


def _jpy_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='JPY' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def _fetch_page(pg, keyword, page):
    """페이지 컨텍스트에서 API 호출 (CF 우회)."""
    return pg.evaluate(
        """async ({kw, page, pmax}) => {
            const u = 'https://api.amiami.com/api/v1.0/items?lang=eng&pagecnt=' + page
                + '&pagemax=' + pmax + '&s_keywords=' + encodeURIComponent(kw);
            const r = await fetch(u, {headers: {'X-User-Key': 'amiami_dev'}});
            if (!r.ok) return {error: r.status};
            const d = await r.json();
            return {items: d.items || [], total: d.search_result?.total_results || 0};
        }""",
        {"kw": keyword, "page": page, "pmax": PAGEMAX},
    )


def collect(queries=None):
    from playwright.sync_api import sync_playwright

    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _jpy_rate(conn)
    if rate is None:
        print("[amiami] 경고: JPY 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                        "AppleWebKit/537.36 Chrome/121 Safari/537.36"))
        pg = ctx.new_page()
        pg.goto("https://www.amiami.com/eng/", wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(2500)

        for q in queries:
            page_total = 0
            for page in range(1, MAX_PAGES + 1):
                try:
                    data = _fetch_page(pg, q, page)
                except Exception as e:
                    # CF 일시 차단/네트워크로 fetch 실패 → 해당 쿼리 스킵(전체 중단 X)
                    print(f"[amiami] '{q}' p{page} fetch 실패: {str(e).splitlines()[0]}")
                    pg.wait_for_timeout(1500)
                    break
                if data.get("error"):
                    print(f"[amiami] '{q}' p{page} -> HTTP {data['error']}")
                    break
                items = data.get("items", [])
                if not items:
                    break
                for it in items:
                    f = extract_fields(it.get("gname", ""))
                    jpy = it.get("min_price")
                    try:
                        jpy = float(jpy) if jpy not in (None, "") else None
                    except (TypeError, ValueError):
                        jpy = None
                    price_krw = round(jpy * rate) if (jpy and rate) else None
                    rel = it.get("releasedate")
                    rel = rel[:10] if rel else None
                    thumb = it.get("thumb_url")
                    img = (IMG_BASE + thumb) if thumb else None
                    conn.execute(
                        """INSERT OR IGNORE INTO product_listing
                           (source, source_item_id, title_raw, character, genre, maker, line,
                            scale, condition, price, currency, price_krw, is_sold, is_noise,
                            mall_name, category, url, image_url, source_date, description,
                            barcode, query, collected_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "amiami",
                            it.get("gcode"),
                            f["title"], f["character"], f["genre"],
                            it.get("maker_name") or f["maker"], f["line"],
                            f["scale"], "new",
                            jpy, "JPY", price_krw,
                            0,                          # 정가/호가
                            f["is_noise"],
                            "AmiAmi",
                            it.get("salestatus"),
                            f"https://www.amiami.com/eng/detail/?gcode={it.get('gcode')}",
                            img,
                            rel,                        # 발매일
                            None,
                            it.get("jancode"),          # JAN 바코드
                            q,
                            now,
                        ),
                    )
                    page_total += 1
                conn.commit()
                pg.wait_for_timeout(500)
            print(f"[amiami] '{q}' -> {page_total} rows")
            total += page_total

        b.close()

    conn.close()
    print(f"[amiami] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
