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

from storage.db import load_latest_df

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports"

SOURCE_KO = {"naver": "네이버쇼핑", "ebay": "이베이", "wyyyes": "와이스",
             "bunjang": "번개장터", "joongna": "중고나라", "danggn": "당근마켓"}
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
    df["cond_ko"] = df["condition"].map(lambda v: COND_KO.get(v) if pd.notna(v) else None)
    df["desc"] = df["description"].map(lambda v: str(v)[:120] if pd.notna(v) else None)
    listings = (df[["price_krw", "source_ko", "mall_name", "genre", "character_ko",
                    "maker_ko", "status_ko", "title_raw", "url", "image_url", "sdate",
                    "cond_ko", "desc"]]
                .sort_values("price_krw", ascending=False)
                .rename(columns={"character_ko": "character", "maker_ko": "maker"}))
    listings["price_krw"] = listings["price_krw"].astype(int)
    listings["title_raw"] = listings["title_raw"].str.slice(0, 90)

    genres = [g for g in df["genre"].dropna().unique().tolist()]
    sources = sorted(df["source_ko"].dropna().unique().tolist())

    data = {
        "today": today,
        "total": int(len(df)),
        "sold": int((df["is_sold"] == 1).sum()),
        "src_summary": ", ".join(f"{SOURCE_KO.get(s, s)} {n:,}"
                                 for s, n in df["source"].value_counts().items()),
        "median_all": int(df["price_krw"].median()),
        "genres": genres,
        "sources": sources,
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
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family:-apple-system,"Segoe UI",Roboto,"Malgun Gothic",sans-serif; }
  header { padding:18px 24px; border-bottom:1px solid var(--line); position:sticky; top:0;
           background:rgba(15,17,21,.92); backdrop-filter:blur(8px); z-index:10; }
  .htop { display:flex; align-items:baseline; gap:12px; flex-wrap:wrap; }
  h1 { margin:0; font-size:19px; }
  .sub { color:var(--mut); font-size:12.5px; }
  .filters { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; align-items:center; }
  .filters input, .filters select {
    background:#0f1115; border:1px solid var(--line); color:var(--txt);
    border-radius:9px; padding:9px 12px; font-size:13px; }
  .filters input#q { flex:1; min-width:200px; }
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
  .meta { font-size:11px; color:var(--mut); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .tagk { font-size:10.5px; color:var(--acc); background:rgba(91,141,239,.12); padding:2px 7px; border-radius:6px; }
  .cbadge { font-size:10.5px; padding:2px 7px; border-radius:6px; font-weight:600;
            color:#eab308; background:rgba(234,179,8,.14); }
  .pdesc { font-size:11px; color:#aeb4be; line-height:1.4; max-height:30px; overflow:hidden; }
  body.view-grid .pdesc { display:none; }
  .more { display:block; margin:28px auto 0; padding:11px 26px; background:var(--card);
          border:1px solid var(--line); color:var(--txt); border-radius:10px; font-size:13px; cursor:pointer; }
  .empty { text-align:center; color:var(--mut); padding:60px 0; }

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

  /* ── 모바일 ── */
  @media(max-width:640px){
    header { padding:14px 14px; }
    .wrap { padding:14px 14px 50px; }
    .filters { gap:6px; }
    .filters input, .filters select, .viewseg button { padding:10px 11px; font-size:13px; }
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
    <select id="srcF"><option value="">전체 출처</option></select>
    <select id="statF"><option value="">실거래+호가</option><option value="실거래">실거래만</option><option value="호가">호가만</option></select>
    <select id="sortF">
      <option value="price_desc">가격 높은순</option>
      <option value="price_asc">가격 낮은순</option>
    </select>
    <div class="viewseg" id="viewSeg">
      <button data-v="gallery" title="갤러리">▦</button>
      <button data-v="grid" title="작은 그리드">▪▪▪</button>
      <button data-v="list" title="리스트">☰</button>
    </div>
  </div>
  <div class="chips" id="genreChips"></div>
</header>

<div class="wrap">
  <div class="grid" id="grid"></div>
  <div id="emptyMsg"></div>
  <button class="more" id="moreBtn" style="display:none">더 보기</button>
</div>

<script>
const D = __DATA__;
const won = n => (n==null||isNaN(n)) ? "" : Number(n).toLocaleString("ko-KR");
const esc = s => (s==null?"":(""+s)).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

document.getElementById("sub").textContent =
  `${D.today} · 상품 ${D.total.toLocaleString()}건 · 실거래 ${D.sold}건 · 중앙가 ${won(D.median_all)}원 · ${D.src_summary}`;

// 출처 옵션
const srcF=document.getElementById("srcF");
D.sources.forEach(s=>{ const o=document.createElement("option"); o.value=s; o.textContent=s; srcF.appendChild(o); });

// 장르 칩
let genreSel="";
const chipsEl=document.getElementById("genreChips");
function renderChips(){
  chipsEl.innerHTML = [["","전체"],...D.genres.map(g=>[g,g])].map(([v,l])=>
    `<span class="chip ${genreSel===v?'on':''}" data-v="${esc(v)}">${esc(l)}</span>`).join("")
    + `<span class="cnt" id="cnt"></span>`;
  chipsEl.querySelectorAll(".chip").forEach(c=>c.onclick=()=>{ genreSel=c.dataset.v; renderChips(); apply(); });
}

const q=document.getElementById("q"), statF=document.getElementById("statF"),
      sortF=document.getElementById("sortF"), grid=document.getElementById("grid"),
      moreBtn=document.getElementById("moreBtn"), emptyMsg=document.getElementById("emptyMsg");

const PAGE=60; let filtered=[], shown=0;

// 장르별 색상 (다채로운 카드)
const GENRE_COLOR = {"괴수":"#ef4444","공룡":"#22c55e","특촬":"#3b82f6","괴물":"#a855f7","기타":"#6b7280"};
const gColor = g => GENRE_COLOR[g] || "#5b8def";

function card(r){
  const gc = gColor(r.genre);
  const img = r.image_url
    ? `<img class="thumb" loading="lazy" referrerpolicy="no-referrer" src="${esc(r.image_url)}" onerror="this.outerHTML='<div class=ph>🧸</div>'">`
    : `<div class="ph">🧸</div>`;
  const tags = [r.character, r.maker].filter(Boolean).map(t=>`<span class="tagk">${esc(t)}</span>`).join("");
  const badge = r.status_ko==="실거래"
    ? `<span class="badge sold">실거래</span>` : `<span class="badge ask">호가</span>`;
  const gb = r.genre ? `<span class="gbadge">${esc(r.genre)}</span>` : "";
  const cb = r.cond_ko ? `<span class="cbadge">${esc(r.cond_ko)}</span>` : "";
  const dlabel = r.sdate ? (r.status_ko==="실거래" ? "거래 " : "마감 ")+r.sdate : "";
  const meta = [r.source_ko, r.mall_name, dlabel].filter(Boolean).map(esc).join(" · ");
  const desc = r.desc ? `<div class="pdesc">${esc(r.desc)}</div>` : "";
  const titleAttr = r.desc ? ` title="${esc(r.desc)}"` : "";
  return `<a class="pcard" style="--gc:${gc}" href="${esc(r.url||'#')}" target="_blank" rel="noopener"${titleAttr}>
    ${img}
    <div class="pbody">
      <div class="pname">${esc(r.title_raw)}</div>
      <div class="pprice">${won(r.price_krw)}<span style="font-size:12px;color:var(--mut)"> 원</span></div>
      <div class="prow">${badge}${cb}${gb}${tags}</div>
      ${desc}
      <div class="meta">${meta}</div>
    </div></a>`;
}

function apply(){
  const term=q.value.trim().toLowerCase(), sf=srcF.value, st=statF.value;
  filtered = D.listings.filter(r=>
    (!term || (r.title_raw||"").toLowerCase().includes(term) || (r.mall_name||"").toLowerCase().includes(term)) &&
    (!sf || r.source_ko===sf) && (!st || r.status_ko===st) && (!genreSel || r.genre===genreSel));
  const s=sortF.value;
  filtered.sort((a,b)=> s==="price_asc" ? a.price_krw-b.price_krw : b.price_krw-a.price_krw);
  shown=0; grid.innerHTML="";
  const cnt=document.getElementById("cnt"); if(cnt) cnt.textContent=`${filtered.length.toLocaleString()}건`;
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
q.oninput=apply; srcF.onchange=apply; statF.onchange=apply; sortF.onchange=apply;

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

renderChips(); apply();
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
