"""Phase1 분석: 가격분포 / 제조사·라인·캐릭터 랭킹.

호가 기반(네이버). 실거래 앵커(야후/스루가야)는 Phase2.
"""
import pandas as pd

from storage.db import get_conn


def load_df():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM product_listing WHERE price_krw IS NOT NULL AND is_noise=0", conn
    )
    conn.close()
    return df


def remove_outliers_iqr(s: pd.Series) -> pd.Series:
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return s[(s >= lo) & (s <= hi)]


def price_summary(df, group_key):
    rows = []
    for key, g in df.groupby(group_key):
        prices = remove_outliers_iqr(g["price_krw"])
        if len(prices) == 0:
            continue
        rows.append({
            group_key: key,
            "count": len(g),
            "median_krw": round(prices.median()),
            "p25": round(prices.quantile(0.25)),
            "p75": round(prices.quantile(0.75)),
            "min": round(prices.min()),
            "max": round(prices.max()),
        })
    out = pd.DataFrame(rows).sort_values("count", ascending=False)
    return out


def run():
    df = load_df()
    if df.empty:
        print("데이터 없음. 먼저 수집 실행: python -m collectors.api.naver")
        return

    print(f"\n=== 총 {len(df)}건 수집 ===\n")

    # 장르 분포 먼저 (괴수/공룡/특촬 중점)
    print("### 장르별 가격/물량")
    print(price_summary(df, "genre").to_markdown(index=False))
    print()

    for key in ("maker", "line", "character"):
        sub = df[df[key].notna()]
        if sub.empty:
            print(f"[{key}] 매칭된 데이터 없음 (사전 확장 필요)\n")
            continue
        print(f"### {key} 별 가격/물량")
        print(price_summary(sub, key).to_markdown(index=False))
        print()

    # 인기 랭킹 (물량 = 노출 빈도 프록시)
    print("### 인기 랭킹 (캐릭터, 물량 기준)")
    pop = (df[df["character"].notna()]
           .groupby("character").size().sort_values(ascending=False)
           .reset_index(name="listings"))
    if not pop.empty:
        print(pop.to_markdown(index=False))
    print()


if __name__ == "__main__":
    run()
