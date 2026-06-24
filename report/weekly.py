"""주간 리포트 생성기 -> reports/report_<날짜>.md

현재 DB 스냅샷 기준 마크다운 리포트 작성. 자동화 시 collect 후 호출.
"""
import datetime
from pathlib import Path

import pandas as pd

from storage.db import get_conn
from analysis.price import price_summary, remove_outliers_iqr

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports"


def load():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM product_listing WHERE price_krw IS NOT NULL AND is_noise=0", conn)
    conn.close()
    return df


def section(title, df_table):
    return f"## {title}\n\n{df_table.to_markdown(index=False)}\n"


def build(today=None):
    today = today or datetime.date.today().isoformat()
    df = load()
    if df.empty:
        print("데이터 없음. 먼저 collect.")
        return

    parts = [f"# 소프비 시장 리포트 — {today}\n",
             f"- 분석 대상: {len(df):,}건 (노이즈 제외, 호가 기준)",
             f"- 소스: 네이버 쇼핑 (국내 새제품)\n"]

    # 장르
    parts.append(section("장르별 가격/물량", price_summary(df, "genre")))

    # 제조사 (물량 5+ 만)
    mk = df[df["maker"].notna()]
    if not mk.empty:
        parts.append(section("제조사별 가격/물량", price_summary(mk, "maker")))

    # 캐릭터
    ch = df[df["character"].notna()]
    if not ch.empty:
        parts.append(section("캐릭터별 가격/물량", price_summary(ch, "character")))

    # 인기 랭킹
    pop = (ch.groupby("character").size().sort_values(ascending=False)
             .reset_index(name="listings"))
    parts.append(section("인기 랭킹 (물량 기준)", pop))

    # 고가 TOP 10
    top = (df.sort_values("price_krw", ascending=False)
             .head(10)[["price_krw", "genre", "maker", "title_raw"]].copy())
    top["price_krw"] = top["price_krw"].map(lambda x: f"{int(x):,}")
    top["title_raw"] = top["title_raw"].str.slice(0, 40)
    parts.append(section("고가 매물 TOP 10", top))

    # 가격대 분포
    bins = [0, 30_000, 100_000, 300_000, 1_000_000, float("inf")]
    labels = ["~3만", "3~10만", "10~30만", "30~100만", "100만+"]
    df["tier"] = pd.cut(df["price_krw"], bins=bins, labels=labels)
    dist = df.groupby("tier", observed=True).size().reset_index(name="count")
    parts.append(section("가격대 구간 분포", dist))

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"report_{today}.md"
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"[report] 작성 완료 -> {out}")
    return out


if __name__ == "__main__":
    build()
