"""HTML 대시보드 생성기 -> reports/dashboard.html

브라우저로 바로 여는 단독 HTML. 차트(Chart.js CDN) + 정렬 가능한 표.
상품별 최신 스냅샷 기준(중복 제거). 자동화 시 collect 후 호출.

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


def _records(df):
    return df.to_dict(orient="records")


def build(today=None):
    today = today or datetime.date.today().isoformat()
    df = load_latest_df()
    if df.empty:
        print("데이터 없음. 먼저 collect.")
        return

    genre = price_summary(df, "genre")
    maker = price_summary(df[df["maker"].notna()], "maker") if df["maker"].notna().any() else pd.DataFrame()
    char = price_summary(df[df["character"].notna()], "character") if df["character"].notna().any() else pd.DataFrame()

    pop = (df[df["character"].notna()].groupby("character").size()
           .sort_values(ascending=False).reset_index(name="listings"))

    bins = [0, 30_000, 100_000, 300_000, 1_000_000, float("inf")]
    labels = ["~3만", "3~10만", "10~30만", "30~100만", "100만+"]
    tier = (pd.cut(df["price_krw"], bins=bins, labels=labels)
            .value_counts().reindex(labels).fillna(0).astype(int))

    top = (df.sort_values("price_krw", ascending=False)
             .head(20)[["price_krw", "genre", "maker", "character", "title_raw", "url"]]
             .copy())
    top["title_raw"] = top["title_raw"].str.slice(0, 50)

    data = {
        "today": today,
        "total": int(len(df)),
        "genre": _records(genre),
        "maker": _records(maker),
        "char": _records(char),
        "pop": _records(pop),
        "tier_labels": labels,
        "tier_counts": [int(x) for x in tier.tolist()],
        "top": _records(top),
        "median_all": int(df["price_krw"].median()),
        "max_all": int(df["price_krw"].max()),
    }

    html = _TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    print(f"[html] 작성 완료 -> {out}")
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
  :root { --bg:#0f1115; --card:#1a1d24; --line:#2a2e38; --txt:#e6e8ec; --mut:#9aa0ab; --acc:#5b8def; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--txt);
         font-family:-apple-system,"Segoe UI",Roboto,"Malgun Gothic",sans-serif; }
  header { padding:24px 28px; border-bottom:1px solid var(--line); }
  h1 { margin:0; font-size:20px; }
  .sub { color:var(--mut); font-size:13px; margin-top:4px; }
  .wrap { padding:24px 28px; max-width:1200px; margin:0 auto; }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin-bottom:24px; }
  .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:16px 18px; }
  .card .k { color:var(--mut); font-size:12px; }
  .card .v { font-size:24px; font-weight:600; margin-top:6px; }
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
  td.t { text-align:left; white-space:normal; max-width:380px; }
  a { color:var(--acc); text-decoration:none; }
  .scroll { max-height:420px; overflow:auto; }
  .num { font-variant-numeric:tabular-nums; }
</style>
</head>
<body>
<header>
  <h1>소프비 시장 대시보드</h1>
  <div class="sub" id="sub"></div>
</header>
<div class="wrap">
  <div class="cards" id="cards"></div>

  <div class="grid2">
    <section><h2>인기 캐릭터 (물량)</h2><canvas id="popChart"></canvas></section>
    <section><h2>가격대 구간 분포</h2><canvas id="tierChart"></canvas></section>
  </div>

  <section><h2>장르별 중앙가 (KRW)</h2><canvas id="genreChart"></canvas></section>

  <section><h2>제조사별 가격/물량</h2><div class="scroll"><table id="makerTbl"></table></div></section>
  <section><h2>캐릭터별 가격/물량</h2><div class="scroll"><table id="charTbl"></table></div></section>
  <section><h2>고가 매물 TOP 20</h2><div class="scroll"><table id="topTbl"></table></div></section>
</div>

<script>
const D = __DATA__;
const won = n => (n==null||isNaN(n)) ? "" : Number(n).toLocaleString("ko-KR");

document.getElementById("sub").textContent =
  `${D.today} · 분석 ${D.total.toLocaleString()}건 (상품별 최신, 호가 기준) · 네이버 쇼핑`;

const cards = [
  ["분석 상품 수", D.total.toLocaleString()],
  ["전체 중앙가", won(D.median_all)+"원"],
  ["최고가", won(D.max_all)+"원"],
  ["캐릭터 종류", D.pop.length],
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

// ---- 정렬 가능한 표 ----
function makeTable(el, rows, cols) {
  if(!rows.length){ el.innerHTML = "<tr><td>데이터 없음</td></tr>"; return; }
  let sortKey=cols[0].k, asc=false;
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
        if(c.link&&r.url) return `<td class="t"><a href="${r.url}" target="_blank">${v??""}</a></td>`;
        if(c.t) return `<td class="t">${v??""}</td>`;
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
  {k:"count",label:"물량"},{k:"median_krw",label:"중앙가",money:1},
  {k:"p25",label:"p25",money:1},{k:"p75",label:"p75",money:1},
  {k:"min",label:"최저",money:1},{k:"max",label:"최고",money:1}];

makeTable(makerTbl, D.maker, [{k:"maker",label:"제조사"},...priceCols]);
makeTable(charTbl, D.char, [{k:"character",label:"캐릭터"},...priceCols]);
makeTable(topTbl, D.top, [
  {k:"price_krw",label:"가격",money:1},
  {k:"genre",label:"장르"},{k:"maker",label:"제조사"},{k:"character",label:"캐릭터"},
  {k:"title_raw",label:"상품명",t:1,link:1}]);
</script>
</body>
</html>"""


if __name__ == "__main__":
    build()
