"""다나와 수집기 — 국내 가격비교(최저가) **호가**.

국내 새제품/해외직구 최저가 비교사이트. 네이버쇼핑 보완 = 국내 판매가 기준선↑.
평범한 requests(CF/인증 불필요). 통화 KRW.

기술: `search.danawa.com/dsearch.php?k1=<kw>&module=goods` HTML.
  `<li class="prod_item" id="productItem<cmpny>_<prod>">` 단위 분할 →
   - 이름 `<p class="prod_name"><a>...</a>` (<b>강조 제거)
   - 최저가 첫 `<p class="price_sect">...<strong>47,980</strong>원`
   - 링크 go_link_goods.php, 이미지 <img alt=...>
  이름 접두어 `[중고]`→condition used, `[해외]`→해외직구(new). is_sold=0(판매 호가).

⚠️ 다나와는 취미용품 카테고리에 소프비 다수(CCP·카이요도·반다이 등) + 해외직구·중고샵 혼재.
⚠️ 광고/스폰서 item 섞일 수 있음. 저빈도 호출.

  python run.py danawa
"""
import datetime
import html as _html
import re
import time
import urllib.parse as up

import requests

from storage.db import get_conn, init_db
from normalize.extract import extract_fields

SEARCH_URL = "https://search.danawa.com/dsearch.php"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept-Language": "ko,en;q=0.8"}

# 국내 검색어 (bunjang/naver QUERIES와 동계열)
QUERIES = [
    "소프비 괴수", "소프비 고질라", "소프비 울트라맨", "소프비 공룡",
    "소프비 가면라이더", "괴수 소프비", "소프비 피규어",
    "무비몬스터 고질라", "이치방쿠지 소프비", "제일복권 소프비",
]
MAX_PAGES = 3          # query당 최대 ~120건 (page당 40)
REQUEST_DELAY = 0.8    # 보수적

_ITEM_RE = re.compile(
    r'<li[^>]*\bid="productItem([A-Za-z0-9_]+)"[^>]*class="prod_item[^"]*".*?(?=<li[^>]*\bid="productItem|<div class="list_btm_paginator)',
    re.S)
_NAME_RE = re.compile(r'<p class="prod_name">\s*<a[^>]*>(.*?)</a>', re.S)
_PRICE_RE = re.compile(r'<p[^>]*class="price_sect"[^>]*>.*?<strong>([\d,]+)</strong>\s*원', re.S)
_LINK_RE = re.compile(r'href="(https://prod\.danawa\.com/bridge/go_link_goods\.php[^"]+)"')
_IMG_RE = re.compile(r'<img\s+src="([^"]+)"', re.S)


def _clean(s):
    return _html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def search(query, page=1):
    params = {"k1": query, "module": "goods", "page": page}
    r = requests.get(SEARCH_URL, headers=HEADERS, params=params, timeout=25)
    r.raise_for_status()
    return r.text


def _parse(html_text):
    out = []
    for m in _ITEM_RE.finditer(html_text):
        item_id, block = m.group(1), m.group(0)
        nm = _NAME_RE.search(block)
        if not nm:
            continue
        name = _clean(nm.group(1))
        if not name:
            continue
        pm = _PRICE_RE.search(block)
        price = float(pm.group(1).replace(",", "")) if pm else None
        lm = _LINK_RE.search(block)
        im = _IMG_RE.search(block)
        img = im.group(1) if im else None
        if img and img.startswith("//"):
            img = "https:" + img
        out.append({
            "id": item_id,
            "name": name,
            "price": price,
            "url": lm.group(1) if lm else None,
            "image": img,
        })
    return out


def collect(queries=None):
    queries = queries or QUERIES
    init_db()
    conn = get_conn()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    total = 0

    for q in queries:
        q_total = 0
        for page in range(1, MAX_PAGES + 1):
            try:
                items = _parse(search(q, page=page))
            except Exception as e:
                print(f"[danawa] '{q}' p{page} 실패: {e} (백오프)")
                time.sleep(3)
                break
            if not items:
                break
            for it in items:
                name = it["name"]
                f = extract_fields(name)
                # 접두어 마커로 중고 식별 (extract가 못 잡는 한글 [중고])
                cond = "used" if re.match(r"\s*\[중고\]", name) else f["condition"]
                conn.execute(
                    """INSERT OR IGNORE INTO product_listing
                       (source, source_item_id, title_raw, character, genre, maker, line,
                        scale, condition, price, currency, price_krw, is_sold, is_noise,
                        mall_name, category, url, image_url, source_date, query, collected_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        "danawa",
                        it["id"],
                        f["title"], f["character"], f["genre"], f["maker"], f["line"],
                        f["scale"], cond,
                        it["price"], "KRW", it["price"],
                        0,                          # 최저가 = 판매 호가
                        f["is_noise"],
                        "다나와",
                        None,
                        it["url"],
                        it["image"],
                        None,                       # 발매일 없음
                        q,
                        now,
                    ),
                )
                q_total += 1
            conn.commit()
            time.sleep(REQUEST_DELAY)
        print(f"[danawa] '{q}' -> {q_total} rows")
        total += q_total

    conn.close()
    print(f"[danawa] done. total {total} rows @ {now}")


if __name__ == "__main__":
    collect()
