"""고가 매물 TOP N + 가격대(tier) 분포. 빈티지/하이엔드 세그먼트 확인용."""
import pandas as pd
from storage.db import get_conn


def run(n=15):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT price_krw, genre, maker, character, title_raw FROM product_listing "
        "WHERE price_krw IS NOT NULL", conn)
    conn.close()

    print(f"\n=== 고가 매물 TOP {n} ===")
    top = df.sort_values("price_krw", ascending=False).head(n)
    for _, r in top.iterrows():
        print(f"{int(r.price_krw):>10,}원  {str(r.genre or '-'):<4} "
              f"{str(r.maker or '-'):<8} {r.title_raw[:42]}")

    # 가격대 구간 분포
    bins = [0, 30_000, 100_000, 300_000, 1_000_000, float("inf")]
    labels = ["~3만", "3~10만", "10~30만", "30~100만", "100만+"]
    df["tier"] = pd.cut(df["price_krw"], bins=bins, labels=labels)
    print("\n=== 가격대 구간 분포 ===")
    dist = df.groupby("tier", observed=True).size().reset_index(name="count")
    print(dist.to_markdown(index=False))


if __name__ == "__main__":
    run()
