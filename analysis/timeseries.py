"""시계열 분석: 수집 스냅샷(collected_at) 누적 기반.

매일 `python run.py collect` 돌리면 같은 상품이 날짜별로 쌓인다.
- 장르/캐릭터별 중앙가 추이
- 신규 등장 / 가격 급변 탐지
데이터가 1일치뿐이면 추이 비교 불가 → 안내만 출력.
"""
import pandas as pd
from storage.db import get_conn


def load():
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT collected_at, genre, character, price_krw FROM product_listing "
        "WHERE price_krw IS NOT NULL AND is_noise=0", conn)
    conn.close()
    df["date"] = pd.to_datetime(df["collected_at"]).dt.date
    return df


def run():
    df = load()
    days = sorted(df["date"].unique())
    print(f"\n=== 시계열 ({len(days)}개 스냅샷일: {days[0]} ~ {days[-1]}) ===")
    if len(days) < 2:
        print("스냅샷이 1일치뿐. 매일 collect 누적하면 추이 분석 가능.")
        print("자동화: python run.py collect 를 /schedule 또는 작업스케줄러로 일 1회.")
        return

    # 장르별 일자 중앙가 피벗
    piv = (df.groupby(["date", "genre"])["price_krw"].median()
             .round().unstack("genre"))
    print("\n### 장르별 일자 중앙가(KRW)")
    print(piv.to_markdown())

    # 최근 2일 변동률
    last2 = piv.tail(2)
    if len(last2) == 2:
        chg = ((last2.iloc[1] - last2.iloc[0]) / last2.iloc[0] * 100).round(1)
        print("\n### 직전일 대비 중앙가 변동률(%)")
        print(chg.to_frame("change_%").to_markdown())


if __name__ == "__main__":
    run()
