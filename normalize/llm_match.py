"""교차언어 상품 매칭 — Claude Code(세션 내 LLM)가 직접 판정. 유료 API 미사용.

문제: 아미아미(일본 정가)는 영문/romaji 제목 + JAN바코드, 국내 중고(와이스/번개)는
한글 제목 + 바코드 없음. 같은 제품을 묶으려면 교차언어 의미 매칭이 필요한데
규칙/퍼지매칭으로는 한계 → LLM 판정. 단, Anthropic 유료 API는 쓰지 않는다.
대신 **이 세션의 Claude Code가 직접** 후보를 읽고 같은제품을 판정해 저장한다
(PLAN §6 "정규화 LLM 추출 = Claude Code 핵심"의 원래 의도).

워크플로 (매 세션):
  1. export_candidates() — 겹치는 genre의 아미아미 정가상품 / 국내 중고 후보를
     읽기 좋은 파일로 덤프.
  2. Claude Code가 두 파일을 읽고 같은제품 쌍을 찾는다.
  3. save_matches([...]) 로 product_match에 적재. premium.py가 상품단위로 계산.

  python run.py match     # 후보 덤프 + 현재 매칭 현황 출력 (판정은 Claude Code가 대화로)

참고: 데이터 특성상(아미아미=현행 신품, 국내=빈티지/제일복권/빅소프비 중고)
SKU 단위 실제 겹침은 적다. 매칭이 적으면 세그먼트 근사(premium.py)가 당분간 유효.
"""
import datetime
import os

from storage.db import get_conn, init_db, load_latest_df

AMIAMI = ("amiami",)
DOMESTIC_USED = ("wyyyes", "bunjang")
JP_USED = ("yahoo_jp",)
# 양측이 함께 존재해 매칭 가능성이 있는 genre (기타는 노이즈 커서 제외)
OVERLAP_GENRES = ["괴수", "특촬", "공룡", "괴물"]
# yahoo_jp는 일본어 제목이라 extract genre가 약함(대부분 기타) → 키워드로 보완 surfacing.
JP_KAIJU_TOKENS = [
    "ゴジラ", "怪獣", "ウルトラ", "仮面ライダー", "ライダー", "グリッドマン",
    "ダイナゼノン", "ガメラ", "ガンダム", "ソフビ", "ムービーモンスター",
    "東宝", "円谷", "メカゴジラ", "キングギドラ", "バルタン",
]

SCRATCH = os.path.join(
    os.environ.get("TEMP", "/tmp"), "figures_match"
)


def _won(v):
    try:
        return f"{int(round(v)):,}" if v is not None and v == v else "?"
    except (TypeError, ValueError):
        return "?"


def export_candidates(out_dir=None):
    """겹치는 genre의 아미아미 앵커/국내 후보를 UTF-8 파일로 덤프. 경로 반환."""
    out_dir = out_dir or SCRATCH
    os.makedirs(out_dir, exist_ok=True)
    df = load_latest_df()
    df = df[df["price_krw"].notna()]
    a = df[(df.source.isin(AMIAMI)) & (df.genre.isin(OVERLAP_GENRES))]
    d = df[(df.source.isin(DOMESTIC_USED)) & (df.genre.isin(OVERLAP_GENRES))]

    # yahoo_jp(일본 중고 실거래): genre가 overlap이거나 제목에 괴수 토큰 포함
    yj = df[df.source.isin(JP_USED)].copy()
    tok = yj["title_raw"].fillna("").apply(
        lambda t: any(k in t for k in JP_KAIJU_TOKENS))
    yj = yj[yj.genre.isin(OVERLAP_GENRES) | tok]

    a_path = os.path.join(out_dir, "amiami_anchors.txt")
    d_path = os.path.join(out_dir, "domestic_candidates.txt")
    y_path = os.path.join(out_dir, "yahoo_jp_candidates.txt")
    with open(a_path, "w", encoding="utf-8") as f:
        for g in OVERLAP_GENRES:
            sub = a[a.genre == g]
            f.write(f"\n##### AMIAMI genre={g} ({len(sub)}) #####\n")
            for _, r in sub.iterrows():
                f.write(f"{r['source_item_id']} | {_won(r['price_krw'])}원 | "
                        f"{r.get('maker') or '?'} | rel={r.get('source_date') or '?'} | "
                        f"{r['title_raw']}\n")
    with open(d_path, "w", encoding="utf-8") as f:
        for g in OVERLAP_GENRES:
            sub = d[d.genre == g]
            f.write(f"\n##### DOMESTIC genre={g} ({len(sub)}) #####\n")
            for _, r in sub.iterrows():
                f.write(f"{r['source']}:{r['source_item_id']} | {_won(r['price_krw'])}원 | "
                        f"{r['title_raw']}\n")
    with open(y_path, "w", encoding="utf-8") as f:
        f.write(f"\n##### YAHOO_JP 일본중고 실거래 ({len(yj)}) #####\n")
        for _, r in yj.iterrows():
            f.write(f"yahoo_jp:{r['source_item_id']} | {_won(r['price_krw'])}원 | "
                    f"{r['title_raw']}\n")
    return a_path, d_path, y_path, len(a), len(d), len(yj)


def save_matches(matches, method="claude-code"):
    """판정된 매칭 적재.

    matches: [{amiami_item_id, used_source, used_item_id, confidence, reason}, ...]
    """
    init_db()
    conn = get_conn()
    now = datetime.datetime.now().isoformat(timespec="seconds")
    n = 0
    for m in matches:
        conn.execute(
            """INSERT OR REPLACE INTO product_match
               (amiami_item_id, used_source, used_item_id, confidence,
                reason, method, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (m["amiami_item_id"], m["used_source"], m["used_item_id"],
             float(m.get("confidence", 1.0)), m.get("reason", ""), method, now),
        )
        n += 1
    conn.commit()
    conn.close()
    return n


def _match_count():
    conn = get_conn()
    try:
        n = conn.execute("SELECT COUNT(*) FROM product_match").fetchone()[0]
    except Exception:
        n = 0
    conn.close()
    return n


def run():
    init_db()
    a_path, d_path, y_path, na, nd, ny = export_candidates()
    print("[match] 후보 덤프 완료 (Claude Code가 읽고 같은제품 판정 → save_matches):")
    print(f"  아미아미 앵커 {na}개: {a_path}")
    print(f"  국내 중고 후보 {nd}개: {d_path}")
    print(f"  야후옥션JP 후보 {ny}개: {y_path}")
    print(f"[match] 현재 product_match {_match_count()}건.")
    print("[match] 새 세션이면 Claude Code에게 '매칭 진행' 요청 → 두 파일 검토 후 적재.")


if __name__ == "__main__":
    run()
