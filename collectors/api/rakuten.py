"""라쿠텐 이치바 수집기 — 일본 신품/중고 **호가**(점포 판매가).

Rakuten Ichiba Item Search API (공식, 무료 applicationId). 통화 JPY → price_krw 환율보정.
- GET app.rakuten.co.jp/services/api/IchibaItem/Search/20220601
- params: applicationId, keyword, format=json, hits(≤30), page(1-100), sort
- 응답: Items[].{itemName,itemPrice,itemUrl,itemCode,shopName,mediumImageUrls,genreId,reviewCount}
  (20220601 버전은 평탄 구조. 구버전 {Items:[{Item:{...}}]}도 방어.)

⚠️ 검색 페이지(search.rakuten.co.jp) HTML은 Akamai 차단 → 공식 API만 길.
⚠️ 라쿠텐은 점포 모음 = 대부분 신품 정가성 호가. 일부 中古 점포 섞임(title로 condition 추정).
   is_sold=0 (호가). 야후옥션(낙찰=실거래)과 보완 관계.

키 발급(무료·즉시, eBay와 달리 심사 없음):
  1. https://webservice.rakuten.co.jp/ 에서 앱 등록 → applicationId 발급
  2. .env 에 RAKUTEN_APP_ID=<id> 추가

  python run.py rakuten   (또는 python -m collectors.api.rakuten)
"""
import datetime
import os
import time

import requests
from dotenv import load_dotenv

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

load_dotenv()

SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
APP_ID = os.getenv("RAKUTEN_APP_ID")

# 아미아미/야후 라인과 겹치는 일본어 검색어 (KEEP IN SYNC: amiami.py / yahoo_jp.py)
QUERIES = [
    "ゴジラ ソフビ", "ウルトラマン ソフビ", "仮面ライダー ソフビ", "怪獣 ソフビ",
    "ムービーモンスター ゴジラ", "一番くじ ゴジラ", "X-PLUS ゴジラ",
    "大怪獣 ソフビ", "ダイナゼノン ソフビ", "グリッドマン ソフビ", "怪獣8号 ソフビ",
]
HITS = 30              # API 최대 30/page
MAX_PAGES = 5          # query당 최대 150건
REQUEST_DELAY = 0.5    # 라쿠텐 권장 1req/sec 미만 보수적


def _jpy_rate(conn):
    row = conn.execute(
        "SELECT rate FROM fx_rate WHERE base='JPY' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    return float(row[0]) if row else None


def search(query, page=1, hits=HITS):
    if not APP_ID:
        raise RuntimeError("RAKUTEN_APP_ID 미설정 (.env 확인, https://webservice.rakuten.co.jp/)")
    r = requests.get(
        SEARCH_URL,
        params={"applicationId": APP_ID, "keyword": query, "format": "json",
                "hits": hits, "page": page, "sort": "standard"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=25,
    )
    r.raise_for_status()
    return r.json()


def _unwrap(node):
    """20220601 평탄 구조 + 구버전 {Item:{...}} 둘 다 지원."""
    return node.get("Item", node) if isinstance(node, dict) else {}


def _image(it):
    imgs = it.get("mediumImageUrls") or it.get("smallImageUrls") or []
    if imgs:
        first = imgs[0]
        url = first.get("imageUrl") if isinstance(first, dict) else first
        # 라쿠텐 썸네일 _ex= 크기파라미터 제거 → 원본
        return url.split("?")[0] if url else None
    return None


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    rate = _jpy_rate(conn)
    if rate is None:
        print("[rakuten] 경고: JPY 환율 없음 -> price_krw 미보정. 먼저 python run.py fx 권장.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    for q in queries:
        q_total = 0
        for page in range(1, MAX_PAGES + 1):
            try:
                data = search(q, page=page)
            except Exception as e:
                print(f"[rakuten] '{q}' p{page} 실패: {e} (백오프)")
                time.sleep(3)
                break
            items = data.get("Items") or []
            if not items:
                break
            for node in items:
                it = _unwrap(node)
                jpy = it.get("itemPrice")
                try:
                    jpy = float(jpy) if jpy not in (None, "") else None
                except (TypeError, ValueError):
                    jpy = None
                price_krw = round(jpy * rate) if (jpy and rate) else None
                name = it.get("itemName", "")
                f = extract_fields(name)
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "rakuten",
                        str(it.get("itemCode")),
                        f["title"], f["character"], f["genre"], f["maker"], f["line"],
                        f["scale"], f["condition"],
                        jpy, "JPY", price_krw,
                        0,                          # 점포 판매가 = 호가
                        f["is_noise"],
                        it.get("shopName") or "楽天市場",
                        str(it.get("genreId") or ""),
                        it.get("itemUrl"),
                        _image(it),
                        None,                       # 발매일 없음
                        q,
                        now,
                    ),
                )
                q_total += 1
            conn.commit()
            # API 응답의 총 페이지 초과 시 중단
            if page >= int(data.get("pageCount") or MAX_PAGES):
                break
            time.sleep(REQUEST_DELAY)
        print(f"[rakuten] '{q}' -> {q_total} rows")
        total += q_total

    conn.close()
    print(f"[rakuten] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
