"""HTML 상품 대시보드 -> reports/dashboard.html

상품 브라우징 중심. 썸네일 카드 그리드 + 검색/필터/정렬.
- 상품 이미지·가격·실거래/호가·출처·매장 표시, 클릭 시 원본 사이트 이동
- 검색(상품명·매장), 출처/구분/장르 필터, 가격 정렬
상품별 최신 스냅샷 기준(중복 제거).

  python run.py html
"""
import datetime
import json
from pathlib import Path

import pandas as pd

from analysis.premium import compute_premium, compute_product_premium, JP_USED
from storage.db import load_latest_df

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports"

SOURCE_KO = {"naver": "네이버쇼핑", "ebay": "이베이", "wyyyes": "와이스",
             "bunjang": "번개장터", "joongna": "중고나라", "danggn": "당근마켓",
             "amiami": "아미아미", "yahoo_jp": "야후옥션JP", "hlj": "HLJ", "bbts": "BBTS",
             "suruga": "스루가야", "rakuten": "라쿠텐", "danawa": "다나와",
             "hobbysearch": "하비서치", "entearth": "EE"}
CHAR_KO = {
    "Godzilla": "고질라", "Ultraman": "울트라맨", "Kamen Rider": "가면라이더",
    "Dinosaur": "공룡", "Jurassic": "쥬라기", "Gamera": "가메라",
    "King Ghidorah": "킹기도라", "Tyrannosaurus": "티라노", "Baltan": "바루탄",
    "Mothra": "모스라", "Rodan": "라돈", "Mechagodzilla": "메카고질라",
}
MAKER_KO = {
    "Bandai": "반다이", "Banpresto": "반프레스토", "TakaraTomy": "타카라토미",
    "Ensky": "엔스카이", "Kaiyodo": "카이요도", "Medicom": "메디콤",
    "Bullmark": "불마크", "Yutaka": "유타카", "Marmit": "마미트",
    "Marusan": "마루산", "Popy": "포피", "X-Plus": "엑스플러스", "M1go": "M1고",
}
COND_KO = {
    "used_sealed": "미개봉", "used_open": "개봉", "used": "중고",
    "new": "새상품", "prize": "프라이즈",
}


def _ko(d, v):
    return d.get(v, v) if pd.notna(v) else None


def build(today=None):
    today = today or datetime.date.today().isoformat()
    df = load_latest_df()
    if df.empty:
        print("데이터 없음. 먼저 collect.")
        return

    df = df[df["price_krw"].notna()].copy()
    df["source_ko"] = df["source"].map(lambda v: SOURCE_KO.get(v, v))
    df["character_ko"] = df["character"].map(lambda v: _ko(CHAR_KO, v))
    df["maker_ko"] = df["maker"].map(lambda v: _ko(MAKER_KO, v))
    df["status_ko"] = df["is_sold"].map(lambda x: "실거래" if x == 1 else "호가")

    df["sdate"] = df["source_date"].map(lambda v: str(v)[:10] if pd.notna(v) else None)
    # 제목에 박힌 연식 추출 (예: 고질라(1989)) — 빈티지/원형 연도 식별
    df["year"] = df["title_raw"].str.extract(r"(19[5-9]\d|20[0-2]\d)", expand=False)
    df["cond_ko"] = df["condition"].map(lambda v: COND_KO.get(v) if pd.notna(v) else None)
    df["desc"] = df["description"].map(lambda v: str(v)[:120] if pd.notna(v) else None)

    def _datelabel(row):
        s, sold = row["source"], row["is_sold"]
        if s == "amiami":
            return "발매"
        if s == "bunjang":
            return "등록"
        if s == "wyyyes":
            return "거래" if sold == 1 else "마감"
        return ""
    df["datelabel"] = df.apply(_datelabel, axis=1)
    listings = (df[["price_krw", "source", "source_ko", "mall_name", "genre", "character_ko",
                    "maker_ko", "status_ko", "title_raw", "url", "image_url", "sdate",
                    "cond_ko", "desc", "year", "datelabel"]]
                .sort_values("price_krw", ascending=False)
                .rename(columns={"character_ko": "character", "maker_ko": "maker"}))
    listings["price_krw"] = listings["price_krw"].astype(int)
    listings["title_raw"] = listings["title_raw"].str.slice(0, 90)

    genres = [g for g in df["genre"].dropna().unique().tolist()]
    sources = sorted(df["source_ko"].dropna().unique().tolist())

    # 프리미엄율: 상품단위(LLM 매칭) 우선 + 캐릭터 세그먼트 근사(참고). 라벨 한글화.
    prod = compute_product_premium(df)
    for r in prod:
        r["kind"] = "상품"
        r["n_list"] = 1
        r["label"] = (r["label"] or "")[:50]
    # 일본 프리미엄(정가↔일본중고 yahoo_jp) — 상품단위 매칭
    jp = compute_product_premium(df, used_sources=JP_USED)
    for r in jp:
        r["kind"] = "일본"
        r["n_list"] = 1
        r["label"] = (r["label"] or "")[:50]
    seg = compute_premium(df)
    for r in seg:
        r["kind"] = "세그먼트"
        r["label"] = CHAR_KO.get(r["label"], r["label"])
    premium = prod + jp + seg

    # 판매가 추천: 매칭 상품별 시세→권장가 (실거래 우선)
    from analysis.pricing import compute_pricing, FAST_MULT, TOP_MULT
    pricing = compute_pricing(df)
    for r in pricing:
        r["label"] = (r["label"] or "")[:50]

    data = {
        "today": today,
        "total": int(len(df)),
        "sold": int((df["is_sold"] == 1).sum()),
        "src_summary": ", ".join(f"{SOURCE_KO.get(s, s)} {n:,}"
                                 for s, n in df["source"].value_counts().items()),
        "median_all": int(df["price_krw"].median()),
        "genres": genres,
        "sources": sources,
        "premium": premium,
        "pricing": pricing,
        "price_policy": {"fast": FAST_MULT, "top": TOP_MULT},
        "listings": listings.to_dict(orient="records"),
    }

    html = _TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"[html] 작성 완료 -> {out} (상품 {len(listings):,}건)")
    print(f"[html] 브라우저로 열기: start {out}")
    return out


_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>소프비 상품</title>
<style>
  :root { --bg:#0f1115; --card:#1a1d24; --line:#2a2e38; --txt:#e6e8ec; --mut:#9aa0ab;
          --acc:#5b8def; --sold:#22c55e; --ask:#9aa0ab; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt); overflow-x:hidden;
         font-family:-apple-system,"Segoe UI",Roboto,"Malgun Gothic",sans-serif; }
  header { padding:18px 24px; border-bottom:1px solid var(--line); position:sticky; top:0;
           background:rgba(15,17,21,.92); backdrop-filter:blur(8px); z-index:10; }
  .htop { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  h1 { margin:0; font-size:19px; }
  .sub { color:var(--mut); font-size:12.5px; }
  /* 요약 통계 → 칩 + 호버 툴팁 (영역 절약) */
  .subpill { position:relative; display:inline-flex; align-items:center; gap:5px; font-size:12px;
             color:var(--mut); background:#1a1d24; border:1px solid var(--line);
             padding:5px 11px; border-radius:999px; cursor:default; }
  .subpill::before { content:"📊"; font-size:11px; }
  .subpill .sp-main { color:var(--txt); font-weight:600; }
  .subpill .sp-tip { position:absolute; top:132%; left:0; z-index:30;
                     white-space:normal; width:max-content; max-width:min(82vw,360px);
                     background:#1a1d24; border:1px solid var(--line); border-radius:10px;
                     padding:10px 14px; font-size:12px; color:var(--txt); line-height:1.8;
                     box-shadow:0 12px 32px rgba(0,0,0,.5); opacity:0; visibility:hidden;
                     transform:translateY(-4px); transition:opacity .12s, transform .12s; }
  .subpill .sp-tip b { color:var(--acc); font-weight:600; }
  .subpill:hover .sp-tip { opacity:1; visibility:visible; transform:translateY(0); }
  .filters { display:flex; flex-direction:column; gap:10px; margin-top:12px; align-items:stretch; }
  .ftools { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
  .ftools .cnt { margin-left:auto; }
  .filters input {
    background:#0f1115; border:1px solid var(--line); color:var(--txt);
    border-radius:10px; padding:10px 13px; font-size:13px;
    transition:border-color .12s, box-shadow .12s; }
  .filters input::placeholder { color:#5d646f; }
  .filters input:hover { border-color:#3a4150; }
  .filters input:focus { outline:none; border-color:var(--acc); box-shadow:0 0 0 3px rgba(91,141,239,.18); }
  .filters input#q { width:100%; }
  /* 커스텀 셀렉트 (네이티브 화살표 제거 + 캐럿 SVG) */
  .filters select {
    appearance:none; -webkit-appearance:none; -moz-appearance:none;
    background:#1a1d24 url("data:image/svg+xml;charset=utf-8,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239aa0ab' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E") no-repeat right 11px center;
    border:1px solid var(--line); color:var(--txt); border-radius:10px;
    padding:10px 34px 10px 13px; font-size:13px; font-weight:500; cursor:pointer;
    transition:border-color .12s, background-color .12s, box-shadow .12s; }
  .filters select:hover { border-color:#3a4150; background-color:#20242d; }
  .filters select:focus { outline:none; border-color:var(--acc); box-shadow:0 0 0 3px rgba(91,141,239,.18); }
  .filters select option { background:#1a1d24; color:var(--txt); }
  .chips { display:flex; gap:6px; flex-wrap:wrap; margin-top:10px; }
  .chip { font-size:12px; padding:6px 12px; border-radius:999px; border:1px solid var(--line);
          background:#0f1115; color:var(--mut); cursor:pointer; user-select:none; }
  .chip.on { background:var(--acc); color:#fff; border-color:var(--acc); }
  .cnt { color:var(--mut); font-size:12px; margin-left:auto; }
  /* 보기모드 토글 */
  .viewseg { display:inline-flex; border:1px solid var(--line); border-radius:9px; overflow:hidden; }
  .viewseg button { background:#0f1115; border:0; color:var(--mut); padding:9px 12px; font-size:13px;
                    cursor:pointer; }
  .viewseg button.on { background:var(--acc); color:#fff; }
  .wrap { padding:18px 24px 60px; }
  .grid { display:grid; gap:16px; grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); }
  .pcard { background:var(--card); border:1px solid var(--line); border-radius:14px;
           overflow:hidden; text-decoration:none; color:inherit; display:flex; flex-direction:column;
           border-top:3px solid var(--gc,#3b82f6);
           transition:transform .08s, border-color .08s, box-shadow .08s; }
  .pcard:hover { transform:translateY(-3px); border-color:var(--acc); box-shadow:0 8px 22px rgba(0,0,0,.35); }
  .thumb { width:100%; aspect-ratio:1/1; background:#0c0e12; object-fit:cover; display:block; }
  .ph { width:100%; aspect-ratio:1/1; display:flex; align-items:center; justify-content:center;
        color:#3a4250; font-size:34px; background:#0c0e12; }
  .pbody { padding:11px 12px 13px; display:flex; flex-direction:column; gap:7px; min-width:0; }
  .pname { font-size:12.5px; line-height:1.45; height:36px; overflow:hidden; color:var(--txt); }
  .pprice { font-size:17px; font-weight:700; font-variant-numeric:tabular-nums; }
  .prow { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
  .badge { font-size:10.5px; padding:2px 7px; border-radius:6px; font-weight:600; }
  .badge.sold { background:rgba(34,197,94,.16); color:var(--sold); }
  .badge.ask { background:#222633; color:var(--ask); }
  .gbadge { font-size:10.5px; padding:2px 8px; border-radius:6px; font-weight:600;
            color:var(--gc,#3b82f6); background:color-mix(in srgb, var(--gc,#3b82f6) 16%, transparent); }
  /* 출처 뱃지 (색상=출처별) */
  .sbadge { font-size:10.5px; padding:2px 8px; border-radius:6px; font-weight:700;
            color:#fff; background:var(--sc,#5b8def); letter-spacing:.2px; }
  /* 날짜 라인 */
  .dateline { display:flex; align-items:center; gap:4px; font-size:11px; color:var(--mut);
              font-variant-numeric:tabular-nums; }
  .dateline .dlbl { font-weight:600; color:#c0c6d0; }
  .meta { font-size:11px; color:var(--mut); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .tagk { font-size:10.5px; color:var(--acc); background:rgba(91,141,239,.12); padding:2px 7px; border-radius:6px; }
  .cbadge { font-size:10.5px; padding:2px 7px; border-radius:6px; font-weight:600;
            color:#eab308; background:rgba(234,179,8,.14); }
  .ybadge { font-size:10.5px; padding:2px 7px; border-radius:6px; font-weight:600;
            color:#f472b6; background:rgba(244,114,182,.14); }
  .pdesc { font-size:11px; color:#aeb4be; line-height:1.4; max-height:30px; overflow:hidden; }
  body.view-grid .pdesc { display:none; }
  .more { display:block; margin:28px auto 0; padding:11px 26px; background:var(--card);
          border:1px solid var(--line); color:var(--txt); border-radius:10px; font-size:13px; cursor:pointer; }
  .empty { text-align:center; color:var(--mut); padding:60px 0; }

  /* ── 프리미엄 섹션 ── */
  .premium { margin-bottom:22px; }
  .premium .phead { display:flex; align-items:baseline; gap:10px; cursor:pointer; user-select:none;
                    padding:6px 0; }
  .premium .phead h2 { margin:0; font-size:15px; }
  .premium .phead .pnote { color:var(--mut); font-size:11.5px; }
  .premium .phead .caret { margin-left:auto; color:var(--mut); font-size:12px; }
  .prow2 { display:grid; gap:12px; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); margin-top:10px; }
  .pcard2 { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:13px 15px;
            border-left:4px solid var(--gc,#5b8def); }
  .pcard2 .ptitle { font-size:14px; font-weight:700; margin-bottom:8px; display:flex; align-items:center; gap:7px; }
  .pcard2 .ppct { font-size:22px; font-weight:800; font-variant-numeric:tabular-nums; }
  .pcard2 .ppct.hi { color:#ef4444; } .pcard2 .ppct.mid { color:#eab308; } .pcard2 .ppct.lo { color:var(--sold); }
  .pcard2 .pline { font-size:11.5px; color:var(--mut); margin-top:6px; font-variant-numeric:tabular-nums; }
  .pcard2 .pn { font-size:10.5px; color:#6b7280; margin-top:3px; }
  .kbadge { font-size:9.5px; padding:1px 6px; border-radius:5px; font-weight:700; flex:none; }
  .kbadge.prod { background:#16351f; color:#4ade80; border:1px solid #1f5130; }
  .kbadge.seg  { background:#2a2630; color:#a78bfa; border:1px solid #3b3548; }
  .kbadge.real { background:#16351f; color:#4ade80; border:1px solid #1f5130; }
  .kbadge.ask  { background:#2a2630; color:#9ca3af; border:1px solid #3b3548; }
  .kbadge.jp   { background:#2b1d22; color:#fb7185; border:1px solid #4a2530; }
  .premium.collapsed .prow2 { display:none; }
  /* 판매가 추천 카드: 두 추천가 */
  .precos { display:flex; gap:8px; margin-top:2px; }
  .preco { flex:1; background:var(--card); border:1px solid var(--line); border-radius:9px; padding:7px 9px; }
  .preco .lab { font-size:10px; color:var(--mut); margin-bottom:2px; }
  .preco .val { font-size:17px; font-weight:800; font-variant-numeric:tabular-nums; }
  .preco.fast .val { color:var(--sold); } .preco.top .val { color:#eab308; }

  /* ── 보기모드: 작은 그리드(촘촘) ── */
  body.view-grid .grid { grid-template-columns:repeat(auto-fill,minmax(132px,1fr)); gap:11px; }
  body.view-grid .pname { font-size:11.5px; height:32px; }
  body.view-grid .pprice { font-size:14.5px; }
  body.view-grid .tagk { display:none; }

  /* ── 보기모드: 리스트(가로형, 모바일 스캔용) ── */
  body.view-list .grid { grid-template-columns:1fr; gap:10px; }
  body.view-list .pcard { flex-direction:row; border-top:1px solid var(--line); border-left:4px solid var(--gc,#3b82f6); }
  body.view-list .thumb, body.view-list .ph { width:96px; height:96px; aspect-ratio:auto; flex:none; }
  body.view-list .pbody { padding:10px 14px; justify-content:center; flex:1; }
  body.view-list .pname { height:auto; max-height:38px; }

  /* ── 필터 버튼 + 활성 필터 바 ── */
  .fbtn { display:inline-flex; align-items:center; gap:7px; background:#1a1d24; border:1px solid var(--line);
          color:var(--txt); border-radius:10px; padding:10px 14px; font-size:13px; font-weight:600; cursor:pointer;
          transition:border-color .12s, background-color .12s; }
  .fbtn:hover { border-color:#3a4150; background:#20242d; }
  .fbtn svg { color:var(--mut); }
  .fbadge { display:inline-grid; place-items:center; min-width:18px; height:18px; padding:0 5px;
            background:var(--acc); color:#fff; border-radius:999px; font-size:11px; font-weight:700; }
  .fbadge[hidden] { display:none; }
  #bar { align-items:center; }
  #bar .cnt { margin:0 4px 0 0; }
  .fact { display:inline-flex; align-items:center; gap:5px; font-size:12px; padding:5px 10px; border-radius:999px;
          background:rgba(91,141,239,.14); color:#cdd9f7; border:1px solid rgba(91,141,239,.32); cursor:pointer;
          transition:background-color .1s; }
  .fact:hover { background:rgba(91,141,239,.26); }
  .fact .x { color:var(--mut); font-weight:700; }

  /* ── 모달 (바텀시트) ── */
  .mback { position:fixed; inset:0; z-index:100; background:rgba(0,0,0,.55); backdrop-filter:blur(2px);
           display:flex; align-items:center; justify-content:center; padding:20px;
           opacity:0; animation:mfade .15s forwards; }
  .mback[hidden] { display:none; }
  @keyframes mfade { to { opacity:1; } }
  .msheet { width:100%; max-width:460px; max-height:85vh; display:flex; flex-direction:column;
            background:var(--card); border:1px solid var(--line); border-radius:16px; overflow:hidden;
            box-shadow:0 24px 60px rgba(0,0,0,.5); transform:translateY(10px); animation:mrise .18s forwards; }
  @keyframes mrise { to { transform:translateY(0); } }
  .mhead { display:flex; align-items:center; justify-content:space-between;
           padding:16px 18px; border-bottom:1px solid var(--line); }
  .mhead h3 { margin:0; font-size:15px; }
  .mx { background:none; border:0; color:var(--mut); font-size:16px; cursor:pointer; padding:4px 9px; border-radius:8px; }
  .mx:hover { background:#0f1115; color:var(--txt); }
  .mbody { padding:4px 18px 10px; overflow-y:auto; }
  .fgroup { padding:13px 0; border-bottom:1px solid var(--line); }
  .fgroup:last-child { border-bottom:0; }
  .flab { font-size:12px; color:var(--mut); margin-bottom:9px; font-weight:600; }
  .segwrap { display:flex; gap:7px; flex-wrap:wrap; }
  .seg { font-size:12.5px; padding:8px 13px; border-radius:9px; border:1px solid var(--line);
         background:#0f1115; color:var(--mut); cursor:pointer; user-select:none;
         transition:border-color .1s, color .1s, background-color .1s; }
  .seg:hover { border-color:#3a4150; color:var(--txt); }
  .seg.on { background:var(--acc); color:#fff; border-color:var(--acc); font-weight:600; }
  .mfoot { display:flex; gap:10px; padding:14px 18px; border-top:1px solid var(--line); }
  .mbtn { padding:12px; border-radius:10px; font-size:14px; font-weight:700; cursor:pointer; border:1px solid var(--line); }
  .mbtn.ghost { background:#0f1115; color:var(--txt); flex:0 0 auto; padding:12px 18px; }
  .mbtn.ghost:hover { border-color:#3a4150; }
  .mbtn.primary { flex:1; background:var(--acc); color:#fff; border-color:var(--acc); }
  .mbtn.primary:hover { filter:brightness(1.08); }
  body.modal-open { overflow:hidden; }

  /* ── 모바일 ── */
  @media(max-width:640px){
    header { padding:14px 14px; }
    .wrap { padding:14px 14px 50px; }
    .filters { gap:6px; }
    .filters input, .fbtn, .viewseg button { padding:10px 11px; font-size:13px; }
    .mback { align-items:flex-end; padding:0; }
    .msheet { max-width:none; max-height:88vh; border-radius:16px 16px 0 0; }
    .grid { gap:11px; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); }
    body.view-grid .grid { grid-template-columns:repeat(auto-fill,minmax(104px,1fr)); gap:8px; }
    body.view-list .thumb, body.view-list .ph { width:84px; height:84px; }
    h1 { font-size:17px; }
  }
</style>
</head>
<body>
<header>
  <div class="htop">
    <h1>소프비 상품</h1>
    <span class="sub" id="sub"></span>
  </div>
  <div class="filters">
    <input id="q" placeholder="🔍 상품명·매장 검색 (예: 고질라, 울트라맨, 불마크)">
    <div class="ftools">
      <button class="fbtn" id="filterBtn">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"/></svg>
        필터·정렬<span class="fbadge" id="fbadge" hidden></span>
      </button>
      <div class="viewseg" id="viewSeg">
        <button data-v="gallery" title="갤러리">▦</button>
        <button data-v="grid" title="작은 그리드">▪▪▪</button>
        <button data-v="list" title="리스트">☰</button>
      </div>
      <span class="cnt" id="cntTop">0건</span>
    </div>
  </div>
  <div class="chips" id="bar"></div>
</header>

<!-- 필터·정렬 모달 (바텀시트) -->
<div class="mback" id="mback" hidden>
  <div class="msheet" role="dialog" aria-modal="true" aria-label="필터 및 정렬">
    <div class="mhead"><h3>필터 · 정렬</h3><button class="mx" id="mClose" aria-label="닫기">✕</button></div>
    <div class="mbody">
      <div class="fgroup"><div class="flab">정렬</div><div class="segwrap" id="grpSort"></div></div>
      <div class="fgroup"><div class="flab">거래상태</div><div class="segwrap" id="grpStat"></div></div>
      <div class="fgroup"><div class="flab">출처</div><div class="segwrap" id="grpSrc"></div></div>
      <div class="fgroup"><div class="flab">장르</div><div class="segwrap" id="grpGenre"></div></div>
    </div>
    <div class="mfoot">
      <button class="mbtn ghost" id="mReset">초기화</button>
      <button class="mbtn primary" id="mApply">결과 보기</button>
    </div>
  </div>
</div>

<div class="wrap">
  <section class="premium collapsed" id="priceSec" style="display:none">
    <div class="phead" id="prHead">
      <h2>💰 판매가 추천</h2>
      <span class="pnote">매칭 상품별 국내 시세→권장가 · 실거래 우선(없으면 호가) · 빠른회전/고점</span>
      <span class="caret" id="prCaret">▼ 펼치기</span>
    </div>
    <div class="prow2" id="priceRow"></div>
  </section>
  <section class="premium collapsed" id="premiumSec" style="display:none">
    <div class="phead" id="pHead">
      <h2>💹 프리미엄율</h2>
      <span class="pnote">정가(아미아미) 대비 국내 중고가 · 상품단위(LLM 매칭) + 캐릭터 세그먼트 근사</span>
      <span class="caret" id="pCaret">▼ 펼치기</span>
    </div>
    <div class="prow2" id="premiumRow"></div>
  </section>
  <div class="grid" id="grid"></div>
  <div id="emptyMsg"></div>
  <button class="more" id="moreBtn" style="display:none">더 보기</button>
</div>

<script>
const D = __DATA__;
const won = n => (n==null||isNaN(n)) ? "" : Number(n).toLocaleString("ko-KR");
const esc = s => (s==null?"":(""+s)).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

(function(){
  const sub=document.getElementById("sub");
  sub.className="subpill";
  sub.innerHTML =
    `<span class="sp-main">${D.today} · 상품 ${D.total.toLocaleString()}건</span>`
    + `<span class="sp-tip">실거래 <b>${D.sold.toLocaleString()}</b>건 · 중앙가 <b>${won(D.median_all)}</b>원<br>${esc(D.src_summary)}</span>`;
})();

// ── 필터 상태 (모달에서 설정) ──
let srcSel="", statSel="", sortSel="price_desc", genreSel="";
const SORTS=[["price_desc","💰 높은가격순"],["price_asc","💰 낮은가격순"],["date_desc","📅 최신순"],["date_asc","📅 오래된순"]];
const STATS=[["","전체"],["실거래","실거래"],["호가","호가"]];
const SORT_LABEL=Object.fromEntries(SORTS);

// 모달 세그먼트 버튼 렌더
function seg(items, cur){
  return items.map(([v,l])=>`<button class="seg ${cur===v?'on':''}" data-v="${esc(v)}">${esc(l)}</button>`).join("");
}
function bindSeg(id, set){
  document.querySelectorAll("#"+id+" .seg").forEach(b=>b.onclick=()=>{ set(b.dataset.v); renderModal(); apply(); });
}
function renderModal(){
  document.getElementById("grpSort").innerHTML  = seg(SORTS, sortSel);
  document.getElementById("grpStat").innerHTML  = seg(STATS, statSel);
  document.getElementById("grpSrc").innerHTML   = seg([["","전체"],...D.sources.map(s=>[s,s])], srcSel);
  document.getElementById("grpGenre").innerHTML = seg([["","전체"],...D.genres.map(g=>[g,g])], genreSel);
  bindSeg("grpSort", v=>sortSel=v);  bindSeg("grpStat", v=>statSel=v);
  bindSeg("grpSrc",  v=>srcSel=v);   bindSeg("grpGenre",v=>genreSel=v);
}

// 활성 필터 개수 + 바(개별 제거 가능)
function activeCount(){ return (srcSel?1:0)+(statSel?1:0)+(genreSel?1:0)+(sortSel!=="price_desc"?1:0); }
function renderBar(){
  const fb=document.getElementById("fbadge"), n=activeCount();
  if(n){ fb.textContent=n; fb.hidden=false; } else fb.hidden=true;
  const toks=[];
  if(srcSel)   toks.push(`<span class="fact" data-k="src">출처: ${esc(srcSel)} <span class="x">✕</span></span>`);
  if(statSel)  toks.push(`<span class="fact" data-k="stat">${esc(statSel)} <span class="x">✕</span></span>`);
  if(genreSel) toks.push(`<span class="fact" data-k="genre">${esc(genreSel)} <span class="x">✕</span></span>`);
  if(sortSel!=="price_desc") toks.push(`<span class="fact" data-k="sort">${esc(SORT_LABEL[sortSel])} <span class="x">✕</span></span>`);
  document.getElementById("cntTop").textContent = `${(filtered?filtered.length:0).toLocaleString()}건`;
  document.getElementById("bar").innerHTML = toks.join("");
  document.querySelectorAll("#bar .fact").forEach(t=>t.onclick=()=>{
    const k=t.dataset.k;
    if(k==="src")srcSel=""; else if(k==="stat")statSel=""; else if(k==="genre")genreSel=""; else sortSel="price_desc";
    renderModal(); apply();
  });
}

const q=document.getElementById("q"), grid=document.getElementById("grid"),
      moreBtn=document.getElementById("moreBtn"), emptyMsg=document.getElementById("emptyMsg");

const PAGE=60; let filtered=[], shown=0;

// 장르별 색상 (다채로운 카드)
const GENRE_COLOR = {"괴수":"#ef4444","공룡":"#22c55e","특촬":"#3b82f6","괴물":"#a855f7","기타":"#6b7280"};
const gColor = g => GENRE_COLOR[g] || "#5b8def";
// 출처별 색상 (뱃지)
const SOURCE_COLOR = {"naver":"#03c75a","wyyyes":"#f59e0b","bunjang":"#ff4800",
                      "amiami":"#e11d8f","ebay":"#0064d2",
                      "yahoo_jp":"#ff0033","hlj":"#1f6feb","bbts":"#d62828",
                      "suruga":"#7b2ff7","rakuten":"#bf0000","danawa":"#00aab5",
                      "hobbysearch":"#ff8800","entearth":"#6a3d9a"};
const sColor = s => SOURCE_COLOR[s] || "#5b8def";

function card(r){
  const gc = gColor(r.genre);
  const img = r.image_url
    ? `<img class="thumb" loading="lazy" referrerpolicy="no-referrer" src="${esc(r.image_url)}" onerror="this.outerHTML='<div class=ph>🧸</div>'">`
    : `<div class="ph">🧸</div>`;
  const tags = [r.character, r.maker].filter(Boolean).map(t=>`<span class="tagk">${esc(t)}</span>`).join("");
  const sb = `<span class="sbadge" style="--sc:${sColor(r.source)}">${esc(r.source_ko)}</span>`;
  const badge = r.status_ko==="실거래"
    ? `<span class="badge sold">실거래</span>` : `<span class="badge ask">호가</span>`;
  const gb = r.genre ? `<span class="gbadge">${esc(r.genre)}</span>` : "";
  const yb = r.year ? `<span class="ybadge">${esc(r.year)}</span>` : "";
  const cb = r.cond_ko ? `<span class="cbadge">${esc(r.cond_ko)}</span>` : "";
  const dline = r.sdate
    ? `<div class="dateline">📅 <span class="dlbl">${esc(r.datelabel||"")}</span> ${esc(r.sdate)}</div>` : "";
  const meta = r.mall_name ? `<div class="meta">🏬 ${esc(r.mall_name)}</div>` : "";
  const desc = r.desc ? `<div class="pdesc">${esc(r.desc)}</div>` : "";
  const titleAttr = r.desc ? ` title="${esc(r.desc)}"` : "";
  return `<a class="pcard" style="--gc:${gc}" href="${esc(r.url||'#')}" target="_blank" rel="noopener"${titleAttr}>
    ${img}
    <div class="pbody">
      <div class="prow">${sb}${badge}</div>
      <div class="pname">${esc(r.title_raw)}</div>
      <div class="pprice">${won(r.price_krw)}<span style="font-size:12px;color:var(--mut)"> 원</span></div>
      <div class="prow">${cb}${yb}${gb}${tags}</div>
      ${dline}
      ${meta}
      ${desc}
    </div></a>`;
}

function apply(){
  const term=q.value.trim().toLowerCase();
  filtered = D.listings.filter(r=>
    (!term || (r.title_raw||"").toLowerCase().includes(term) || (r.mall_name||"").toLowerCase().includes(term)) &&
    (!srcSel || r.source_ko===srcSel) && (!statSel || r.status_ko===statSel) && (!genreSel || r.genre===genreSel));
  const s=sortSel;
  filtered.sort((a,b)=>{
    if(s==="price_asc") return a.price_krw-b.price_krw;
    if(s==="price_desc") return b.price_krw-a.price_krw;
    // 날짜순: 값 없는 항목은 항상 뒤로, 동일 날짜는 가격 높은순
    const da=a.sdate||"", db=b.sdate||"";
    if(!da && !db) return b.price_krw-a.price_krw;
    if(!da) return 1;
    if(!db) return -1;
    if(da===db) return b.price_krw-a.price_krw;
    return s==="date_asc" ? (da<db?-1:1) : (da<db?1:-1);
  });
  shown=0; grid.innerHTML="";
  renderBar();
  emptyMsg.innerHTML = filtered.length ? "" : `<div class="empty">검색 결과 없음</div>`;
  renderMore();
}
function renderMore(){
  const next=filtered.slice(shown, shown+PAGE);
  grid.insertAdjacentHTML("beforeend", next.map(card).join(""));
  shown+=next.length;
  moreBtn.style.display = shown<filtered.length ? "block" : "none";
}
moreBtn.onclick=renderMore;
// 무한 스크롤
window.addEventListener("scroll",()=>{
  if(shown<filtered.length && window.innerHeight+window.scrollY >= document.body.offsetHeight-600) renderMore();
});
q.oninput=apply;

// ── 필터 모달 열기/닫기 ──
const mback=document.getElementById("mback");
function openModal(){ renderModal(); mback.hidden=false; document.body.classList.add("modal-open"); }
function closeModal(){ mback.hidden=true; document.body.classList.remove("modal-open"); }
document.getElementById("filterBtn").onclick=openModal;
document.getElementById("mClose").onclick=closeModal;
document.getElementById("mApply").onclick=closeModal;
document.getElementById("mReset").onclick=()=>{ srcSel="";statSel="";sortSel="price_desc";genreSel=""; renderModal(); apply(); };
mback.onclick=e=>{ if(e.target===mback) closeModal(); };
document.addEventListener("keydown",e=>{ if(e.key==="Escape"&&!mback.hidden) closeModal(); });

// ── 보기모드 토글 (모바일 기본 갤러리, 선택 기억) ──
const VIEWS=["gallery","grid","list"];
const viewSeg=document.getElementById("viewSeg");
function setView(v){
  if(!VIEWS.includes(v)) v="gallery";
  document.body.classList.remove("view-gallery","view-grid","view-list");
  document.body.classList.add("view-"+v);
  viewSeg.querySelectorAll("button").forEach(b=>b.classList.toggle("on", b.dataset.v===v));
  try{ localStorage.setItem("wyv", v); }catch(e){}
}
viewSeg.querySelectorAll("button").forEach(b=>b.onclick=()=>setView(b.dataset.v));
let saved="gallery"; try{ saved=localStorage.getItem("wyv")||"gallery"; }catch(e){}
setView(saved);

// 섹션 표시 토글 (현재 미사용 → 숨김). 다시 쓰려면 true 로.
const SHOW_PREMIUM=false, SHOW_PRICING=false;

// ── 프리미엄 섹션 렌더 ──
(function(){
  if(!SHOW_PREMIUM) return;
  const sec=document.getElementById("premiumSec");
  if(!D.premium || !D.premium.length) return;
  sec.style.display="";
  const cls = p => p>=200?"hi":(p>=100?"mid":"lo");
  document.getElementById("premiumRow").innerHTML = D.premium.map(p=>{
    const gc=gColor(p.genre);
    const arrow = p.diff_krw>=0?"▲":"▼";
    const kindBadge = p.kind==="상품"
      ? `<span class="kbadge prod">상품</span>`
      : (p.kind==="일본"
        ? `<span class="kbadge jp">🇯🇵 일본</span>`
        : `<span class="kbadge seg">세그먼트</span>`);
    const sample = p.kind==="세그먼트"
      ? `표본: 정가 ${p.n_list} · 중고 ${p.n_used}건`
      : (p.kind==="일본"
        ? `표본: 일본중고 ${p.n_used}건 (상품단위 매칭)`
        : `표본: 중고 ${p.n_used}건 (상품단위 매칭)`);
    const usedLabel = p.kind==="일본" ? "일본중고" : "중고";
    return `<div class="pcard2" style="--gc:${gc}">
      <div class="ptitle">${kindBadge}${esc(p.label)}${p.genre?`<span class="gbadge">${esc(p.genre)}</span>`:""}</div>
      <div class="ppct ${cls(p.premium_pct)}">${p.premium_pct}%</div>
      <div class="pline">정가 ${won(p.list_krw)} → ${usedLabel} ${won(p.used_krw)}원 <span style="color:${p.diff_krw>=0?'#ef4444':'#22c55e'}">${arrow}${won(Math.abs(p.diff_krw))}</span></div>
      <div class="pn">${sample}</div>
    </div>`;
  }).join("");
  const head=document.getElementById("pHead"), caret=document.getElementById("pCaret");
  let open=false; try{ open=localStorage.getItem("wyp")==="1"; }catch(e){}
  const sync=()=>{ sec.classList.toggle("collapsed",!open); caret.textContent=open?"▲ 접기":"▼ 펼치기"; };
  head.onclick=()=>{ open=!open; sync(); try{localStorage.setItem("wyp",open?"1":"0");}catch(e){} };
  sync();
})();

// ── 판매가 추천 섹션 렌더 ──
(function(){
  if(!SHOW_PRICING) return;
  const sec=document.getElementById("priceSec");
  if(!D.pricing || !D.pricing.length) return;
  sec.style.display="";
  document.getElementById("priceRow").innerHTML = D.pricing.map(p=>{
    const gc=gColor(p.genre);
    const bBadge = p.basis==="실거래"
      ? `<span class="kbadge real">실거래</span>`
      : `<span class="kbadge ask">호가</span>`;
    const sample = `표본: 실거래 ${p.n_sold} · 호가 ${p.n_ask}건`;
    const vsList = p.list_krw
      ? `정가 ${won(p.list_krw)}원 대비 <b>${p.vs_list_pct}%</b>`
      : `정가 미상`;
    // 일본 매입시세(yahoo_jp 실거래) → 한일 직구 차익
    const jpLine = p.jp_buy_krw
      ? `<div class="pline">🇯🇵 일본매입 ${won(p.jp_buy_krw)}원 → 한일차익 <b style="color:${p.jp_margin_pct>=0?'#fb7185':'#22c55e'}">${p.jp_margin_pct>=0?'+':''}${p.jp_margin_pct}%</b> <span class="pn">(일본중고 ${p.n_jp}건)</span></div>`
      : ``;
    return `<div class="pcard2" style="--gc:${gc}">
      <div class="ptitle">${bBadge}${esc(p.label)}${p.genre?`<span class="gbadge">${esc(p.genre)}</span>`:""}</div>
      <div class="pline">시세 ${won(p.market_krw)}원 · ${vsList}</div>
      <div class="precos">
        <div class="preco fast"><div class="lab">⚡ 빠른회전</div><div class="val">${won(p.fast_krw)}</div></div>
        <div class="preco top"><div class="lab">📈 고점</div><div class="val">${won(p.top_krw)}</div></div>
      </div>
      ${jpLine}
      <div class="pn">${sample}</div>
    </div>`;
  }).join("");
  const head=document.getElementById("prHead"), caret=document.getElementById("prCaret");
  let open=false; try{ open=localStorage.getItem("wypr")==="1"; }catch(e){}
  const sync=()=>{ sec.classList.toggle("collapsed",!open); caret.textContent=open?"▲ 접기":"▼ 펼치기"; };
  head.onclick=()=>{ open=!open; sync(); try{localStorage.setItem("wypr",open?"1":"0");}catch(e){} };
  sync();
})();

apply();
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
