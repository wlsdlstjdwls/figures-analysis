"""프리미엄율 분석: 정가(아미아미) 대비 국내 중고가(와이스/번개).

  premium% = 국내 중고 중앙가 / 일본 정가 중앙가 * 100

매칭 한계 (중요):
- 아미아미만 바코드 보유. 국내 중고(와이스/번개)엔 바코드 없음 →
  상품 단위 정밀 매칭 불가. 게다가 아미아미=영문 / 국내=한글 제목이라
  제목 퍼지매칭도 교차언어라 신뢰도 낮음.
- 그래서 v1은 **정규화된 character(×maker) 세그먼트 단위** 근사치다.
  같은 캐릭터 안에서도 상품 편차가 크므로 "대략 얼마나 붙나" 신호로만 본다.
- 상품 단위 정밀 프리미엄은 LLM 매칭 도입이 다음 단계 (PLAN §2.3, NEXT_STEPS 1순위).

  python run.py premium
"""
import pandas as pd

from storage.db import get_conn, load_latest_df

AMIAMI = ("amiami",)
DOMESTIC_USED = ("wyyyes", "bunjang")     # 국내 중고
JP_USED = ("yahoo_jp",)                   # 일본 중고 실거래(낙찰)


def load_matches_df():
    """product_match 테이블 로드. 없으면 빈 DataFrame."""
    conn = get_conn()
    try:
        df = pd.read_sql_query("SELECT * FROM product_match", conn)
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


def compute_product_premium(df=None, min_confidence=0.7, used_sources=DOMESTIC_USED):
    """LLM 매칭(product_match) 기반 상품단위 프리미엄.

      premium% = 중고가 / 일본 정가 * 100   (매칭된 상품 쌍별)

    used_sources로 어느 진영 중고를 볼지 선택:
      DOMESTIC_USED → 국내 프리미엄, JP_USED → 일본 프리미엄(정가 대비 일본 중고).
    같은 아미아미 상품에 매물 여러 건이면 중고가는 중앙값으로 집계.
    매칭 테이블이 비었으면 빈 리스트 반환(→ run()이 세그먼트 근사로 폴백).
    """
    matches = load_matches_df()
    if matches.empty:
        return []
    matches = matches[matches["confidence"] >= min_confidence]
    matches = matches[matches["used_source"].isin(used_sources)]
    if matches.empty:
        return []

    if df is None:
        df = load_latest_df()
    df = df[df["price_krw"].notna()]
    amiami = df[df["source"].isin(AMIAMI)].set_index("source_item_id")
    dom = df[df["source"].isin(used_sources)].set_index(["source", "source_item_id"])

    rows = []
    for aid, grp in matches.groupby("amiami_item_id"):
        if aid not in amiami.index:
            continue
        a = amiami.loc[aid]
        if isinstance(a, pd.DataFrame):       # 혹시 중복 index
            a = a.iloc[0]
        list_krw = a["price_krw"]
        if not list_krw or list_krw <= 0:
            continue
        used_prices = []
        for _, m in grp.iterrows():
            key = (m["used_source"], m["used_item_id"])
            if key in dom.index:
                d = dom.loc[key]
                if isinstance(d, pd.DataFrame):
                    d = d.iloc[0]
                if pd.notna(d["price_krw"]):
                    used_prices.append(float(d["price_krw"]))
        if not used_prices:
            continue
        used_med = float(pd.Series(used_prices).median())
        rows.append({
            "label": a["title_raw"],
            "list_krw": int(round(list_krw)),
            "used_krw": int(round(used_med)),
            "premium_pct": round(used_med / list_krw * 100),
            "diff_krw": int(round(used_med - list_krw)),
            "n_used": len(used_prices),
            "genre": a.get("genre") if pd.notna(a.get("genre")) else None,
            "image_url": a.get("image_url") if pd.notna(a.get("image_url")) else None,
        })
    rows.sort(key=lambda r: r["premium_pct"], reverse=True)
    return rows


def _iqr(s: pd.Series) -> pd.Series:
    if len(s) < 4:
        return s
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    return s[(s >= q1 - 1.5 * iqr) & (s <= q3 + 1.5 * iqr)]


def _seg_stats(prices: pd.Series):
    p = _iqr(prices.dropna())
    if p.empty:
        return None
    return {"median": int(round(p.median())), "n": int(len(prices))}


def compute_premium(df=None, keys=("character",), min_each=3):
    """세그먼트별 정가 vs 중고 프리미엄율. keys 단위로 양쪽 다 min_each 이상일 때만."""
    if df is None:
        df = load_latest_df()
    df = df[df["price_krw"].notna()].copy()
    keys = list(keys)

    amiami = df[df["source"].isin(AMIAMI)]
    dom = df[df["source"].isin(DOMESTIC_USED)]

    # 세그먼트 대표 이미지/장르 (중고 우선, 없으면 아미아미)
    rows = []
    a_groups = {k: g for k, g in amiami.groupby(keys, dropna=True)}
    d_groups = {k: g for k, g in dom.groupby(keys, dropna=True)}
    for key in sorted(set(a_groups) & set(d_groups)):
        ag, dg = a_groups[key], d_groups[key]
        if len(ag) < min_each or len(dg) < min_each:
            continue
        a, d = _seg_stats(ag["price_krw"]), _seg_stats(dg["price_krw"])
        if not a or not d or a["median"] <= 0:
            continue
        label = key if isinstance(key, str) else " · ".join(str(x) for x in key)
        rep = dg.iloc[0]
        rows.append({
            "label": label,
            "list_krw": a["median"],          # 일본 정가 중앙가
            "used_krw": d["median"],          # 국내 중고 중앙가
            "premium_pct": round(d["median"] / a["median"] * 100),
            "diff_krw": d["median"] - a["median"],
            "n_list": a["n"],
            "n_used": d["n"],
            "genre": rep.get("genre") if pd.notna(rep.get("genre")) else None,
            "image_url": rep.get("image_url") if pd.notna(rep.get("image_url")) else None,
        })
    rows.sort(key=lambda r: r["premium_pct"], reverse=True)
    return rows


def _print_prod(prod, title):
    print(f"\n=== {title} ===\n")
    tbl = pd.DataFrame(prod)[["label", "list_krw", "used_krw", "premium_pct",
                              "diff_krw", "n_used"]]
    tbl["label"] = tbl["label"].str.slice(0, 45)
    tbl.columns = ["상품", "정가(원)", "중고中(원)", "프리미엄%", "차익(원)", "중고n"]
    print(tbl.to_markdown(index=False))
    print(f"※ product_match {len(prod)}개 상품.")


def run():
    prod = compute_product_premium()
    if prod:
        _print_prod(prod, "국내 프리미엄율 (상품단위, 정가↔국내중고)")
    jp = compute_product_premium(used_sources=JP_USED)
    if jp:
        _print_prod(jp, "일본 프리미엄율 (상품단위, 정가↔일본중고 yahoo_jp)")
    if prod or jp:
        print("\n※ 매칭 추가는 python run.py match.")

    rows = compute_premium()
    if not rows and not prod:
        print("프리미엄 계산 가능한 세그먼트 없음 (아미아미 정가 ↔ 국내 중고 겹치는 캐릭터 부족).")
        print("LLM 상품 매칭부터: python run.py match (ANTHROPIC_API_KEY 필요).")
        return
    if rows:
        print("\n=== 프리미엄율 (캐릭터 세그먼트 근사, 참고용) ===\n")
        tbl = pd.DataFrame(rows)[["label", "list_krw", "used_krw", "premium_pct",
                                  "diff_krw", "n_list", "n_used"]]
        tbl.columns = ["캐릭터", "정가中(엔→원)", "중고中(원)", "프리미엄%", "차익(원)", "정가n", "중고n"]
        print(tbl.to_markdown(index=False))
        if not prod:
            print("\n※ 세그먼트 근사치. 상품단위 정밀화는 python run.py match (LLM 매칭).")


if __name__ == "__main__":
    run()
