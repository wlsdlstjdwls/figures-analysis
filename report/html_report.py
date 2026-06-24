"""HTML 대시보드 생성기 -> reports/dashboard.html

브라우저로 바로 여는 단독 HTML. 차트 + 정렬/검색 가능한 표.
- 한글 라벨 (캐릭터/제조사/출처)
- 매장(판매처) 표시, 상품 클릭 시 원본 사이트 이동
- 출처(네이버/이베이/와이스) 표기 + 실거래/호가 구분
- 가격 용어(중앙가/하위25%/상위25%) 설명 포함
- 전체 상품 검색

상품별 최신 스냅샷 기준(중복 제거).

  python run.py html
"""
import datetime
import json
from pathlib import Path

import pandas as pd

from storage.db import load_latest_df
from analysis.price import price_summary

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports"

# ── 한글 표시 사전 ───────────────────────────────────────────
SOURCE_KO = {"naver": "네이버쇼핑", "ebay": "이베이", "wyyyes": "와이스"}
CHAR_KO = {
    "Godzilla": "고질라", "Ultraman": "울트라맨", "Kamen Rider": "가면라이더",
    "Dinosaur": "공룡", "Jurassic": "쥬라기", "Gamera": "가메라",
    "King Ghidorah": "킹기도라", "Tyrannosaurus": "티라노사우루스",
    "Baltan": "바루탄", "Mothra": "모스라", "Rodan": "라돈", "Mechagodzilla": "메카고질라",
}
MAKER_KO = {
    "Bandai": "반다이", "Banpresto": "반프레스토", "TakaraTomy": "타카라토미",
    "Ensky": "엔스카이", "Kaiyodo": "카이요도", "Medicom": "메디콤",
    "Bullmark": "불마크", "Yutaka": "유타카", "Marmit": "마미트",
    "Marusan": "마루산", "Popy": "포피", "X-Plus": "엑스플러스", "M1go": "M1고",
}


def _ko(d, v):
    return d.get(v, v)


def _records(df):
    return df.to_dict(orient="records")


def _group_sources(df, key):
    """그룹별 기여 출처(한글) 리스트."""
    out = {}
    for k, g in df.groupby(key):
        srcs = sorted(g["source"].dropna().unique())
        out[k] = ", ".join(_ko(SOURCE_KO, s) for s in srcs)
    return out


def _attach_sources(summary, df, key):
    smap = _group_sources(df, key)
    summary = summary.copy()
    summary["sources"] = summary[key].map(smap)
    return summary


def build(today=None):
    today = today or datetime.date.today().isoformat()
    df = load_latest_df()
    if df.empty:
        print("데이터 없음. 먼저 collect.")
        return

    # 캐릭터/제조사 한글 컬럼
    df["character_ko"] = df["character"].map(lambda v: _ko(CHAR_KO, v) if pd.notna(v) else v)
    df["maker_ko"] = df["maker"].map(lambda v: _ko(MAKER_KO, v) if pd.notna(v) else v)
    df["source_ko"] = df["source"].map(lambda v: _ko(SOURCE_KO, v))
    df["status_ko"] = df["is_sold"].map(lambda x: "실거래" if x == 1 else "호가")

    genre = _attach_sources(price_summary(df, "genre"), df, "genre")

    mk = df[df["maker"].notna()]
    maker = _attach_sources(price_summary(mk, "maker"), mk, "maker") if not mk.empty else pd.DataFrame()
    if not maker.empty:
        maker["maker"] = maker["maker"].map(lambda v: _ko(MAKER_KO, v))

    ch = df[df["character"].notna()]
    char = _attach_sources(price_summary(ch, "character"), ch, "character") if not ch.empty else pd.DataFrame()
    if not char.empty:
        char["character"] = char["character"].map(lambda v: _ko(CHAR_KO, v))

    pop = (ch.groupby("character_ko").size()
           .sort_values(ascending=False).reset_index(name="listings")
           .rename(columns={"character_ko": "character"}))

    bins = [0, 30_000, 100_000, 300_000, 1_000_000, float("inf")]
    labels = ["~3만", "3~10만", "10~30만", "30~100만", "100만+"]
    tier = (pd.cut(df["price_krw"], bins=bins, labels=labels)
            .value_counts().reindex(labels).fillna(0).astype(int))

    # 전체 상품(검색용) — 노이즈 제외 이미 적용됨
    listings = (df[["price_krw", "source_ko", "mall_name", "genre",
                    "character_ko", "status_ko", "title_raw", "url"]]
                .sort_values("price_krw", ascending=False)
                .rename(columns={"character_ko": "character"})
                .copy())
    listings["title_raw"] = listings["title_raw"].str.slice(0, 70)

    sold_n = int((df["is_sold"] == 1).sum())
    src_summary = ", ".join(f"{_ko(SOURCE_KO, s)} {n:,}"
                            for s, n in df["source"].value_counts().items())

    data = {
        "today": today,
        "total": int(len(df)),
        "sold": sold_n,
        "src_summary": src_summary,
        "genre": _records(genre),
        "maker": _records(maker),
        "char": _records(char),
        "pop": _records(pop),
        "tier_labels": labels,
        "tier_counts": [int(x) for x in tier.tolist()],
        "listings": _records(listings),
        "median_all": int(df["price_krw"].median()),
        "max_all": int(df["price_krw"].max()),
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
<title>소프비 시장 대시보드</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
  :root { --bg:#0f1115; --card:#1a1d24; --line:#2a2e38; --txt:#e6e8ec; --mut:#9aa0ab; --acc:#5b8def; --sold:#22c55e; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family:-apple-system,"Segoe UI",Roboto,"Malgun Gothic",sans-serif; }
  header { padding:24px 28px; border-bottom:1px solid var(--line); }
  h1 { margin:0; font-size:20px; }
  .sub { color:var(--mut); font-size:13px; margin-top:4px; }
  .wrap { padding:24px 28px; max-width:1240px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:14px; margin-bottom:18px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
  .card .k { color:var(--mut); font-size:12px; }
  .card .v { font-size:24px; font-weight:600; margin-top:6px; }
  .legend { background:#15181f; border:1px solid var(--line); border-radius:10px; padding:12px 16px;
            font-size:12.5px; color:var(--mut); margin-bottom:22px; line-height:1.7; }
  .legend b { color:var(--txt); }
  section { background:var(--card); border:1px solid var(--line); border-radius:12px;
            padding:18px 20px; margin-bottom:22px; }
  h2 { font-size:15px; margin:0 0 14px; }
  .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:22px; }
  @media(max-width:820px){ .grid2{ grid-template-columns:1fr; } }
  canvas { max-height:300px; }
  table { width:100%; border-collapse:collapse; font-size:13px; }
  th,td { padding:8px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; }
  th:first-child,td:first-child { text-align:left; }
  th { color:var(--mut); cursor:pointer; user-select:none; position:sticky; top:0; background:var(--card); }
  th:hover { color:var(--txt); }
  td.t { text-align:left; white-space:normal; max-width:340px; }
  td.l { text-align:left; }
  a { color:var(--acc); text-decoration:none; }
  a:hover { text-decoration:underline; }
  .scroll { max-height:440px; overflow:auto; }
  .num { font-variant-numeric:tabular-nums; }
  .tag { font-size:11px; padding:2px 7px; border-radius:6px; background:#222633; color:var(--mut); }
  .tag.sold { background:rgba(34,197,94,.15); color:var(--sold); }
  .src { font-size:11px; color:var(--mut); }
  .searchbar { display:flex; gap:10px; margin-bottom:12px; align-items:center; flex-wrap:wrap; }
  .searchbar input, .searchbar select { background:#0f1115; border:1px solid var(--line); color:var(--txt);
            border-radius:8px; padding:8px 12px; font-size:13px; }
  .searchbar input { flex:1; min-width:200px; }
  .count { color:var(--mut); font-size:12px; }
</style>
</head>
<body>
<header>
  <h1>소프비 시장 대시보드</h1>
  <div class="sub" id="sub"></div>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>

  <div class="legend">
    <b>용어</b> · <b>중앙가(median)</b>: 가격을 줄세웠을 때 한가운데 값(평균보다 이상치에 덜 흔들림).
    · <b>하위25%(p25)</b>: 싼 쪽에서 25% 지점 — 이보다 싼 매물이 1/4.
    · <b>상위25%(p75)</b>: 비싼 쪽 25% 지점 — 이보다 비싼 매물이 1/4. (p25~p75 사이가 "보통 가격대")
    · <b>출처</b>: 가격 근거 사이트. <b>실거래</b>=실제 낙찰/판매가(와이스), <b>호가</b>=파는 사람이 부른 값(네이버 등).
  </div>

  <div class="grid2">
    <section><h2>인기 캐릭터 (물량)</h2><canvas id="popChart"></canvas></section>
    <section><h2>가격대 구간 분포</h2><canvas id="tierChart"></canvas></section>
  </div>

  <section><h2>장르별 중앙가 (원)</h2><canvas id="genreChart"></canvas></section>

  <section><h2>제조사별 가격 · 물량 · 출처</h2><div class="scroll"><table id="makerTbl"></table></div></section>
  <section><h2>캐릭터별 가격 · 물량 · 출처</h2><div class="scroll"><table id="charTbl"></table></div></section>

  <section>
    <h2>상품 검색</h2>
    <div class="searchbar">
      <input id="q" placeholder="상품명·매장 검색 (예: 고질라, 울트라맨)">
      <select id="srcF"><option value="">전체 출처</option></select>
      <select id="statF"><option value="">전체</option><option value="실거래">실거래</option><option value="호가">호가</option></select>
      <span class="count" id="cnt"></span>
    </div>
    <div class="scroll"><table id="listTbl"></table></div>
  </section>
</div>

<script>
const D = __DATA__;
const won = n => (n==null||isNaN(n)) ? "" : Number(n).toLocaleString("ko-KR");

document.getElementById("sub").textContent =
  `${D.today} · 분석 ${D.total.toLocaleString()}건 (상품별 최신) · 실거래 ${D.sold}건 · 출처: ${D.src_summary}`;

const cards = [
  ["분석 상품 수", D.total.toLocaleString()],
  ["실거래(낙찰) 건수", D.sold.toLocaleString()],
  ["전체 중앙가", won(D.median_all)+"원"],
  ["최고가", won(D.max_all)+"원"],
];
document.getElementById("cards").innerHTML = cards.map(
  ([k,v])=>`<div class="card"><div class="k">${k}</div><div class="v num">${v}</div></div>`).join("");

const GRID = "#2a2e38", TXT = "#9aa0ab";
Chart.defaults.color = TXT; Chart.defaults.borderColor = GRID;

new Chart(popChart, { type:"bar",
  data:{ labels:D.pop.map(r=>r.character),
    datasets:[{ label:"물량", data:D.pop.map(r=>r.listings), backgroundColor:"#5b8def" }] },
  options:{ indexAxis:"y", plugins:{legend:{display:false}} } });

new Chart(tierChart, { type:"doughnut",
  data:{ labels:D.tier_labels,
    datasets:[{ data:D.tier_counts,
      backgroundColor:["#3b82f6","#22c55e","#eab308","#f97316","#ef4444"] }] },
  options:{ plugins:{legend:{position:"right"}} } });

new Chart(genreChart, { type:"bar",
  data:{ labels:D.genre.map(r=>r.genre),
    datasets:[{ label:"중앙가(원)", data:D.genre.map(r=>r.median_krw), backgroundColor:"#22c55e" }] },
  options:{ plugins:{legend:{display:false}} } });

// ---- 정렬 가능한 집계표 ----
function makeTable(el, rows, cols) {
  if(!rows.length){ el.innerHTML = "<tr><td>데이터 없음</td></tr>"; return; }
  let sortKey=cols.find(c=>c.def)?.k || cols[0].k, asc=false;
  function render(){
    const sorted=[...rows].sort((a,b)=>{
      let x=a[sortKey], y=b[sortKey];
      if(typeof x==="number"&&typeof y==="number") return asc?x-y:y-x;
      x=(""+x); y=(""+y); return asc?x.localeCompare(y):y.localeCompare(x);
    });
    el.innerHTML =
      "<thead><tr>"+cols.map(c=>`<th data-k="${c.k}">${c.label}${sortKey===c.k?(asc?" ▲":" ▼"):""}</th>`).join("")+"</tr></thead>"+
      "<tbody>"+sorted.map(r=>"<tr>"+cols.map(c=>{
        let v=r[c.k];
        if(c.src) return `<td class="l"><span class="src">${v??""}</span></td>`;
        if(c.l) return `<td class="l">${v??""}</td>`;
        if(c.money) v=won(v);
        else if(typeof v==="number") v=v.toLocaleString();
        return `<td class="num">${v??""}</td>`;
      }).join("")+"</tr>").join("")+"</tbody>";
    el.querySelectorAll("th").forEach(th=>th.onclick=()=>{
      const k=th.dataset.k; if(k===sortKey) asc=!asc; else { sortKey=k; asc=false; } render();
    });
  }
  render();
}

const priceCols=[
  {k:"count",label:"물량",def:1},{k:"median_krw",label:"중앙가",money:1},
  {k:"p25",label:"하위25%",money:1},{k:"p75",label:"상위25%",money:1},
  {k:"min",label:"최저",money:1},{k:"max",label:"최고",money:1},
  {k:"sources",label:"출처",src:1}];

makeTable(makerTbl, D.maker, [{k:"maker",label:"제조사"},...priceCols]);
makeTable(charTbl, D.char, [{k:"character",label:"캐릭터"},...priceCols]);

// ---- 상품 검색 표 ----
const L = D.listings;
const srcF=document.getElementById("srcF"), statF=document.getElementById("statF"),
      q=document.getElementById("q"), cnt=document.getElementById("cnt"), listTbl=document.getElementById("listTbl");
[...new Set(L.map(r=>r.source_ko))].forEach(s=>{
  const o=document.createElement("option"); o.value=s; o.textContent=s; srcF.appendChild(o);
});
let lsortKey="price_krw", lasc=false;
function renderList(){
  const term=q.value.trim().toLowerCase(), sf=srcF.value, st=statF.value;
  let rows=L.filter(r=>
    (!term || (r.title_raw||"").toLowerCase().includes(term) || (r.mall_name||"").toLowerCase().includes(term)) &&
    (!sf || r.source_ko===sf) && (!st || r.status_ko===st));
  rows=[...rows].sort((a,b)=>{
    let x=a[lsortKey],y=b[lsortKey];
    if(typeof x==="number"&&typeof y==="number") return lasc?x-y:y-x;
    x=(""+x);y=(""+y); return lasc?x.localeCompare(y):y.localeCompare(x);
  });
  cnt.textContent=`${rows.length.toLocaleString()}건`;
  const view=rows.slice(0,500);
  const cols=[
    {k:"price_krw",label:"가격"},{k:"status_ko",label:"구분"},{k:"source_ko",label:"출처"},
    {k:"mall_name",label:"매장"},{k:"genre",label:"장르"},{k:"character",label:"캐릭터"},
    {k:"title_raw",label:"상품명(클릭=이동)"}];
  listTbl.innerHTML=
    "<thead><tr>"+cols.map(c=>`<th data-k="${c.k}">${c.label}${lsortKey===c.k?(lasc?" ▲":" ▼"):""}</th>`).join("")+"</tr></thead>"+
    "<tbody>"+view.map(r=>"<tr>"+
      `<td class="num">${won(r.price_krw)}</td>`+
      `<td class="l"><span class="tag ${r.status_ko==='실거래'?'sold':''}">${r.status_ko}</span></td>`+
      `<td class="l">${r.source_ko}</td>`+
      `<td class="l">${r.mall_name||""}</td>`+
      `<td class="l">${r.genre||""}</td>`+
      `<td class="l">${r.character||""}</td>`+
      (r.url?`<td class="t"><a href="${r.url}" target="_blank">${r.title_raw||""}</a></td>`
            :`<td class="t">${r.title_raw||""}</td>`)+
    "</tr>").join("")+"</tbody>";
  if(rows.length>500) cnt.textContent+=` (상위 500건 표시)`;
  listTbl.querySelectorAll("th").forEach(th=>th.onclick=()=>{
    const k=th.dataset.k; if(k===lsortKey) lasc=!lasc; else { lsortKey=k; lasc=false; } renderList();
  });
}
q.oninput=renderList; srcF.onchange=renderList; statF.onchange=renderList;
renderList();
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
