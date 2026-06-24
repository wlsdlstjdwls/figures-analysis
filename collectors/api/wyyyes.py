"""WYYYES(와이스) 수집기 — 국내 컬렉터 라이브 거래 앱.

비공식 JSON API (역분석, 2026-06-24). 인증 불필요.
base: https://wyyyes.com/r0.app/discovery/

- auctionHistoryFeed?category=figure  -> 최근 낙찰 피드(20건 고정, 페이지네이션 X).
    amountPaid = **낙찰가 = 국내 실거래가**. 주기적 폴링으로 누적(자동화 daily).
- auctions/v2?category=figure&...      -> 진행중 경매. lastBidPrice(현재가)/binPrice(즉시구매)=호가.

PLAN §10.5. 야후 폐쇄·eBay sold 게이트로 비어있던 국내 실거래 앵커를 메우는 소스.
ToS·저빈도 원칙(§3.1) 준수. 가격 단위 KRW.

  python run.py wyyyes
"""
import datetime
import time

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

BASE = "https://wyyyes.com/r0.app/discovery"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# 소프비/괴수 중심 + 전 분야. figure가 메인 카테고리.
CATEGORIES = ["figure"]
ACTIVE_LIMIT = 100
REQUEST_DELAY = 0.5


def _get(path):
    r = requests.get(f"{BASE}/{path}", headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json().get("result", [])


def _condition_from_compositions(comps):
    comps = comps or []
    if "unopened" in comps:
        return "used_sealed"
    if "opened" in comps or "used" in comps:
        return "used_open"
    return "used"


def collect(categories=None):
    categories = categories or CATEGORIES
    init_db()
    conn = get_conn()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total_sold = total_active = 0

    # 이미 저장된 낙찰 건(확정가) — 자주 폴링해도 중복 누적 안 하도록 스킵용
    sold_seen = {
        r[0] for r in conn.execute(
            "SELECT source_item_id FROM product_listing WHERE source='wyyyes' AND is_sold=1"
        ).fetchall()
    }

    for cat in categories:
        # ── 1) 낙찰 피드 (실거래) ──────────────────────────────
        try:
            feed = _get(f"auctionHistoryFeed?category={cat}")
        except Exception as e:
            print(f"[wyyyes] history '{cat}' 실패: {e}")
            feed = []
        new_sold = 0
        for it in feed:
            sid = it.get("auctionId") or it.get("_id")
            if sid in sold_seen:        # 낙찰가는 확정값 → 1건만 보관
                continue
            sold_seen.add(sid)
            name = it.get("name", "")
            f = extract_fields(name)
            price = it.get("amountPaid")
            new_sold += 1
            conn.execute(
                """INSERT OR IGNORE INTO product_listing
                   (source, source_item_id, title_raw, character, genre, maker, line,
                    scale, condition, price, currency, price_krw, is_sold, is_noise,
                    mall_name, category, url, image_url, source_date, query, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "wyyyes",
                    sid,
                    f["title"], f["character"], f["genre"], f["maker"], f["line"],
                    f["scale"], f["condition"],
                    float(price) if price not in (None, "") else None,
                    "KRW",
                    float(price) if price not in (None, "") else None,
                    1,                      # 낙찰 = 실거래
                    f["is_noise"],
                    it.get("nickname"),     # 판매자(매장)
                    f"wyyyes:{cat}:sold",
                    it.get("redirectUriWeb"),
                    it.get("thumbnail"),
                    it.get("createdAt"),    # 거래(낙찰) 시각
                    f"{cat}-sold",
                    now,
                ),
            )
            total_sold += 1
        conn.commit()
        time.sleep(REQUEST_DELAY)

        # ── 2) 진행중 경매 (호가/현재가) ───────────────────────
        try:
            active = _get(
                f"auctions/v2?category={cat}&limit={ACTIVE_LIMIT}&order=asc&sortField=endAt"
            )
        except Exception as e:
            print(f"[wyyyes] active '{cat}' 실패: {e}")
            active = []
        for it in active:
            stock = it.get("stock") or {}
            name = stock.get("name", "")
            f = extract_fields(name)
            # 현재가(lastBidPrice) 우선, 없으면 즉시구매가(binPrice)
            price = it.get("lastBidPrice") or stock.get("binPrice")
            seller = (stock.get("seller") or {}).get("nickname")
            conn.execute(
                """INSERT OR IGNORE INTO product_listing
                   (source, source_item_id, title_raw, character, genre, maker, line,
                    scale, condition, price, currency, price_krw, is_sold, is_noise,
                    mall_name, category, url, image_url, source_date, query, collected_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "wyyyes",
                    it.get("_id"),
                    f["title"], f["character"], f["genre"], f["maker"], f["line"],
                    f["scale"], _condition_from_compositions(stock.get("compositions")),
                    float(price) if price not in (None, "") else None,
                    "KRW",
                    float(price) if price not in (None, "") else None,
                    0,                      # 진행중 = 호가
                    f["is_noise"],
                    seller,
                    f"wyyyes:{cat}:active",
                    f"https://wyyyes.com/timeAuction/{it.get('_id')}",
                    stock.get("thumbnail"),
                    it.get("endAt"),        # 경매 마감 예정
                    f"{cat}-active",
                    now,
                ),
            )
            total_active += 1
        conn.commit()
        time.sleep(REQUEST_DELAY)
        print(f"[wyyyes] '{cat}' -> 낙찰 신규 {new_sold}/{len(feed)} / 진행중 {len(active)}")

    conn.close()
    print(f"[wyyyes] done. sold {total_sold}, active {total_active} @ {now}")


if __name__ == "__main__":
    collect()
