"""판매가 추천 엔진: "이 제품 내 숍에 얼마에 팔까?"

기존 데이터를 합쳐 매칭된 상품별 **권장 판매가**를 낸다.

  시세(market) = 국내 중고 실거래 중앙값            (와이스 낙찰 is_sold=1)
                 └ 실거래 없으면 호가 중앙값 폴백     (번개/와이스 active is_sold=0)
  추천가 = 시세 × 위치배수
    · 빠른회전(turn) = 시세 × FAST_MULT   (시세 그대로 → 빨리 팔림)
    · 고점(top)      = 시세 × TOP_MULT    (+10% → 천천히 비싸게)

"실거래 우선" 정책: sold가 1건이라도 있으면 sold만으로 시세를 잡는다.
호가는 보통 실거래보다 높게 부풀려져 있어, 섞으면 시세가 위로 휜다.

근거(정가 대비·표본수·basis)를 함께 실어 신뢰도를 눈으로 보게 한다.
매칭(product_match)이 있는 상품만 대상 — 시세를 잡으려면 어떤 제품인지
특정돼야 하기 때문. 매칭 늘수록(run.py match) 커버리지가 커진다.

  python run.py pricing
"""
import pandas as pd

from storage.db import load_latest_df
from analysis.premium import load_matches_df, AMIAMI, DOMESTIC_USED

# ── 가격 정책 (시세대비 위치) ──
FAST_MULT = 1.00   # 빠른회전: 시세 중앙값 그대로
TOP_MULT = 1.10    # 고점: +10%
ROUND_TO = 1000    # 추천가 반올림 단위(원)


def _round(v: float) -> int:
    return int(round(v / ROUND_TO) * ROUND_TO)


def compute_pricing(df=None, min_confidence=0.7):
    """매칭 상품별 권장 판매가 리스트. premium과 같은 매칭 테이블을 공유."""
    matches = load_matches_df()
    if matches.empty:
        return []
    matches = matches[matches["confidence"] >= min_confidence]
    if matches.empty:
        return []

    if df is None:
        df = load_latest_df()
    df = df[df["price_krw"].notna()]
    amiami = df[df["source"].isin(AMIAMI)].set_index("source_item_id")
    dom = df[df["source"].isin(DOMESTIC_USED)].set_index(["source", "source_item_id"])

    rows = []
    for aid, grp in matches.groupby("amiami_item_id"):
        if aid not in amiami.index:
            continue
        a = amiami.loc[aid]
        if isinstance(a, pd.DataFrame):
            a = a.iloc[0]
        list_krw = a["price_krw"]
        if not list_krw or list_krw <= 0:
            list_krw = None

        sold, ask = [], []
        for _, m in grp.iterrows():
            key = (m["used_source"], m["used_item_id"])
            if key not in dom.index:
                continue
            d = dom.loc[key]
            if isinstance(d, pd.DataFrame):
                d = d.iloc[0]
            if pd.isna(d["price_krw"]):
                continue
            (sold if int(d.get("is_sold") or 0) == 1 else ask).append(float(d["price_krw"]))

        if not sold and not ask:
            continue
        # 실거래 우선: sold 있으면 sold만, 없으면 ask
        if sold:
            market = float(pd.Series(sold).median())
            basis = "실거래"
        else:
            market = float(pd.Series(ask).median())
            basis = "호가"

        rows.append({
            "label": a["title_raw"],
            "market_krw": int(round(market)),
            "basis": basis,                       # 실거래 / 호가
            "fast_krw": _round(market * FAST_MULT),   # 빠른회전 추천가
            "top_krw": _round(market * TOP_MULT),     # 고점 추천가
            "list_krw": int(round(list_krw)) if list_krw else None,   # 일본 정가
            "vs_list_pct": round(market / list_krw * 100) if list_krw else None,
            "n_sold": len(sold),
            "n_ask": len(ask),
            "genre": a.get("genre") if pd.notna(a.get("genre")) else None,
            "image_url": a.get("image_url") if pd.notna(a.get("image_url")) else None,
        })
    # 실거래 근거 있는 것 먼저, 그다음 시세 높은 순
    rows.sort(key=lambda r: (r["basis"] != "실거래", -r["market_krw"]))
    return rows


def run():
    rows = compute_pricing()
    if not rows:
        print("판매가 추천 가능한 상품 없음 (product_match 비어있음).")
        print("먼저 상품 매칭: python run.py match")
        return
    print("\n=== 판매가 추천 (매칭 상품단위, 실거래 우선) ===\n")
    tbl = pd.DataFrame(rows)[["label", "basis", "market_krw", "fast_krw",
                              "top_krw", "vs_list_pct", "n_sold", "n_ask"]]
    tbl["label"] = tbl["label"].str.slice(0, 40)
    tbl.columns = ["상품", "근거", "시세(원)", "빠른회전", "고점(+10%)",
                   "정가대비%", "실거래n", "호가n"]
    print(tbl.to_markdown(index=False))
    n_real = sum(1 for r in rows if r["basis"] == "실거래")
    print(f"\n※ {len(rows)}개 상품 (실거래근거 {n_real} · 호가근거 {len(rows)-n_real}). "
          f"매칭 추가는 python run.py match.")
    print(f"※ 정책: 빠른회전=시세×{FAST_MULT} · 고점=시세×{TOP_MULT} "
          f"(analysis/pricing.py 상수로 조정).")


if __name__ == "__main__":
    run()
