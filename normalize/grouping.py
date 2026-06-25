"""상품그룹 매칭 — source 무관 '같은 제품' 묶기 (반자동, 재실행 가능).

product_match(아미아미 한 방향 앵커)의 일반화. 어느 사이트 매물이든 같은 제품이면
하나의 group_id로 묶는다 → 새↔새 / 중고↔중고 / 새↔중고 비교가 그룹 단위로 가능.

파이프라인 (python run.py group):
  1. migrate_from_matches  — 기존 product_match → product_group/listing_group 로 이관(1회성, 멱등)
  2. auto_block            — character+maker+연식(+라인/상) 일치하는 후보를 고정밀 자동그룹화
  3. export_review         — 애매한 후보(연식 없음 등)는 검수파일로 → Claude Code가 판정
  4. regenerate_product_match — 그룹 → product_match 역생성(중고 매물만) → 기존 premium/pricing/dashboard 호환

새 사이트/새 수집분이 들어와도 이 명령 재실행만 하면 됨. 수동·이관 매칭은 보존되고
자동(auto:blocking) 매칭만 갱신된다.
"""
import datetime
import os
import re

from storage.db import get_conn, init_db, load_latest_df

AMIAMI = "amiami"
# 중고로 취급할 출처 (product_match 호환 역생성 시 used 로 내보냄)
USED_SOURCES = {"wyyyes", "bunjang", "yahoo_jp"}
AUTO_THRESHOLD = 0.8        # 이 이상이면 자동 그룹 확정
REVIEW_MIN = 0.55           # 이 이상~AUTO 미만이면 검수 후보

YEAR_RE = re.compile(r"(?:19|20)\d{2}")
PRIZE_EN_RE = re.compile(r"\b([A-H])\s*Prize\b", re.I)
SCRATCH = os.path.join(os.environ.get("TEMP", "/tmp"), "figures_match")

# ── 라인(제품군) 마커: 같은 character+maker+연식이라도 라인 다르면 다른 제품 ──
# (예: 무비몬스터 고질라2023 ≠ S.H.몬스터아츠 고질라2023). 키워드는 despace 후 비교.
LINE_MARKERS = {
    "moviemonster": ["무비몬스터", "무비몬스터즈", "무비몬스타", "moviemonster"],
    "shma":         ["몬스터아츠", "monsterarts", "s.h.monster", "shmonster",
                     "타마시네이션스", "tamashiination", "tamashiinations",
                     "s.h.모노", "에스에이치몬스터", "shm고지라", "shm고질라"],
    "ichibankuji":  ["이치방쿠지", "이치방", "이치반쇼", "이치반", "ichiban",
                     "제일복권", "쿠지", "kuji", "sofvics", "소프비크스"],
    "banpresto":    ["반프레스토", "banpresto", "반프레", "banpre"],
    "gacha":        ["가챠", "가샤", "gacha", "캡슐토이", "캡슐피규어"],
    "deago":        ["데아고스티니", "deago", "디아고스티니"],
    "deforeal":     ["데포리얼", "deforeal"],
    "gigantic":     ["기간틱", "gigantic"],
    "toho30cm":     ["30cm", "30센치", "30센티", "토호30"],
    "daikaiju":     ["대괴수시리즈", "다이카이주", "daikaiju"],
    "shodo":        ["쇼도", "shodo"],
    "chibi":        ["치비", "chibi"],
}
# 묶음/세트 → 단일 상품 시세 아님. 자동 그룹에서 제외.
BUNDLE_TOKENS = ["일괄", "전종", "일괄판매", "랜덤팩", "벌크", "묶음판매"]


def _despace(s):
    return (s or "").lower().replace(" ", "")


def _line_marker(title):
    nos = _despace(title)
    for marker, kws in LINE_MARKERS.items():
        if any(_despace(k) in nos for k in kws):
            return marker
    return None


def _marker_conflict(anchor_title, cand_title):
    """앵커와 후보의 라인마커 충돌 여부. _score 와 동일 규칙:
    앵커가 라인 명시면 후보도 같은 라인 명시 必, 앵커 무라인인데 후보가 특정 라인이면 충돌."""
    am, cm = _line_marker(anchor_title), _line_marker(cand_title)
    if am and cm and am != cm:
        return True
    if not am and cm:
        return True
    return False


def _is_bundle(title):
    nos = _despace(title)
    return any(_despace(k) in nos for k in BUNDLE_TOKENS)


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def _years(*texts):
    ys = set()
    for t in texts:
        if t:
            ys |= set(YEAR_RE.findall(t))
    return ys


def _prize(text):
    """제일복권/이치방쿠지 상(賞) 식별자. 'A상'/'A Prize'→'A', 라스트원→'LAST'."""
    if not text:
        return None
    low = text.lower()
    m = re.search(r"([A-Ha-h])\s*상", text)
    if m:
        return m.group(1).upper()
    if "라스트원" in text or "last one" in low:
        return "LAST"
    m = PRIZE_EN_RE.search(text)
    if m:
        return m.group(1).upper()
    return None


def _sig(row):
    """매물 한 건의 매칭 시그니처."""
    title = row.get("title_raw") or ""
    return {
        "character": row.get("character") or None,
        "maker": row.get("maker") or None,
        "line": row.get("line") or None,
        "years": _years(title),
        "prize": _prize(title),
        "barcode": (row.get("barcode") or "").strip() or None,
        "marker": _line_marker(title),
        "bundle": _is_bundle(title),
    }


def _score(a, c):
    """앵커 a 시그니처 vs 후보 c 시그니처 → (점수, 근거). 0=불일치."""
    # 바코드 동일 → 즉시 확정
    if a["barcode"] and c["barcode"] and a["barcode"] == c["barcode"]:
        return 0.99, f"barcode={a['barcode']}"
    if not a["character"] or not a["maker"]:
        return 0.0, ""
    if c["character"] != a["character"] or c["maker"] != a["maker"]:
        return 0.0, ""
    if c["bundle"]:                     # 묶음/일괄 → 단일 시세 아님
        return 0.0, ""
    # 라인 마커 규칙 (제품군 혼입 차단):
    #  - 앵커에 라인이 있으면 후보도 같은 라인을 '명시'해야 함 (양성 확인).
    #    인기 character+maker+연식(예: 고질라2023)은 제품군이 수십종이라
    #    라인 명시 없이는 자동 매칭 불가.
    #  - 앵커에 라인이 없는데 후보가 특정 라인이면 거부.
    if a["marker"]:
        if c["marker"] != a["marker"]:
            return 0.0, ""
    elif c["marker"]:
        return 0.0, ""
    score = 0.5
    reasons = [f"char={a['character']}", f"maker={a['maker']}"]
    ay, cy = a["years"], c["years"]
    if ay and cy:
        if ay & cy:
            score += 0.35
            reasons.append("year=" + ",".join(sorted(ay & cy)))
        else:
            return 0.0, ""          # 연식 충돌 → 다른 제품
    if a["line"] and c["line"] and a["line"] == c["line"]:
        score += 0.15
        reasons.append(f"line={a['line']}")
    if a["prize"] and c["prize"]:
        if a["prize"] == c["prize"]:
            score += 0.1
            reasons.append(f"prize={a['prize']}")
        else:
            return 0.0, ""          # 상(賞) 충돌 → 다른 상품
    return min(score, 0.99), ", ".join(reasons)


# ────────────────────────────────────────────────────────────────
def _ensure_group(conn, anchor_source, anchor_item_id, sig, canonical):
    """앵커에 해당하는 그룹을 찾거나 만들어 group_id 반환. 앵커 자신도 멤버로 등록."""
    row = conn.execute(
        "SELECT id FROM product_group WHERE anchor_source=? AND anchor_item_id=?",
        (anchor_source, anchor_item_id),
    ).fetchone()
    if row:
        return row[0]
    conn.execute(
        """INSERT INTO product_group
           (canonical, character, maker, line, year, barcode,
            anchor_source, anchor_item_id, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (canonical, sig["character"], sig["maker"], sig["line"],
         ",".join(sorted(sig["years"])) or None, sig["barcode"],
         anchor_source, anchor_item_id, _now()),
    )
    gid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    # 앵커 자신을 멤버로
    conn.execute(
        """INSERT OR IGNORE INTO listing_group
           (source, source_item_id, group_id, confidence, method, reason, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (anchor_source, anchor_item_id, gid, 1.0, "anchor", "anchor", _now()),
    )
    return gid


def _add_member(conn, source, item_id, gid, conf, method, reason, protect=True):
    """멤버 등록. protect=True면 수동/이관 매칭은 덮어쓰지 않음."""
    if protect:
        ex = conn.execute(
            "SELECT method FROM listing_group WHERE source=? AND source_item_id=?",
            (source, item_id),
        ).fetchone()
        if ex and not (ex[0] or "").startswith("auto"):
            return False        # 수동/seed 보존
    conn.execute(
        """INSERT OR REPLACE INTO listing_group
           (source, source_item_id, group_id, confidence, method, reason, created_at)
           VALUES (?,?,?,?,?,?,?)""",
        (source, item_id, gid, conf, method, reason, _now()),
    )
    return True


# ────────────────────────────────────────────────────────────────
def migrate_from_matches(conn):
    """기존 product_match → 그룹으로 이관 (멱등). 아미아미 앵커별 그룹 생성."""
    df = load_latest_df()
    amiami = {r["source_item_id"]: r for _, r in df[df.source == AMIAMI].iterrows()}
    used = {(r["source"], r["source_item_id"]): r
            for _, r in df[df.source != AMIAMI].iterrows()}
    matches = conn.execute(
        "SELECT amiami_item_id, used_source, used_item_id, confidence, reason, method "
        "FROM product_match"
    ).fetchall()
    n_groups = n_members = 0
    for m in matches:
        aid = m["amiami_item_id"]
        a = amiami.get(aid)
        if a is None:
            continue
        sig = _sig(a)
        # 라인마커 충돌(옛 seed 오매칭: MMS 앵커에 SHMA/쿠지 등) 차단
        cand = used.get((m["used_source"], m["used_item_id"]))
        if cand is not None and _marker_conflict(a.get("title_raw"),
                                                 cand.get("title_raw")):
            continue
        gid = _ensure_group(conn, AMIAMI, aid, sig, a.get("title_raw"))
        n_groups += 1
        if _add_member(conn, m["used_source"], m["used_item_id"], gid,
                       m["confidence"], "seed:product_match", m["reason"] or ""):
            n_members += 1
    conn.commit()
    return n_groups, n_members


def auto_block(conn):
    """character+maker+연식(+라인/상/바코드) 고정밀 자동 그룹화."""
    # 재실행: 이전 자동매칭만 제거(수동/seed/anchor 보존) 후 다시 계산
    conn.execute("DELETE FROM listing_group WHERE method='auto:blocking'")
    conn.commit()
    df = load_latest_df()
    df = df[df["character"].notna() & df["maker"].notna()]
    anchors = df[df.source == AMIAMI]
    cands = df[df.source != AMIAMI]

    # (character, maker) 블록으로 후보군 축소
    from collections import defaultdict
    blocks = defaultdict(list)
    for _, c in cands.iterrows():
        blocks[(c["character"], c["maker"])].append(c)

    assigned = ambiguous = 0
    for _, a in anchors.iterrows():
        asig = _sig(a)
        block = blocks.get((asig["character"], asig["maker"]), [])
        if not block:
            continue
        gid = None
        for c in block:
            csig = _sig(c)
            sc, reason = _score(asig, csig)
            if sc < AUTO_THRESHOLD:
                continue
            # 다른 앵커와 모호하지 않은지: 같은 블록 내 다른 amiami 앵커도 동점이면 보류
            rivals = anchors[(anchors["character"] == asig["character"]) &
                             (anchors["maker"] == asig["maker"])]
            best_other = 0.0
            for _, r in rivals.iterrows():
                if r["source_item_id"] == a["source_item_id"]:
                    continue
                rs, _ = _score(_sig(r), csig)
                best_other = max(best_other, rs)
            if best_other >= sc:        # 다른 앵커가 같거나 더 잘 맞음 → 모호
                ambiguous += 1
                continue
            if gid is None:
                gid = _ensure_group(conn, AMIAMI, a["source_item_id"], asig,
                                    a.get("title_raw"))
            if _add_member(conn, c["source"], c["source_item_id"], gid,
                           round(sc, 2), "auto:blocking", reason):
                assigned += 1
    conn.commit()
    return assigned, ambiguous


def export_review(conn, out_dir=None, limit=400):
    """자동 임계 미달(REVIEW_MIN~AUTO) 후보를 검수파일로 덤프 → Claude Code 판정용."""
    out_dir = out_dir or SCRATCH
    os.makedirs(out_dir, exist_ok=True)
    df = load_latest_df()
    df = df[df["character"].notna() & df["maker"].notna()]
    anchors = df[df.source == AMIAMI]
    cands = df[df.source != AMIAMI]
    grouped = {(r[0], r[1]) for r in
               conn.execute("SELECT source, source_item_id FROM listing_group")}

    from collections import defaultdict
    blocks = defaultdict(list)
    for _, c in cands.iterrows():
        if (c["source"], c["source_item_id"]) in grouped:
            continue
        blocks[(c["character"], c["maker"])].append(c)

    lines = []
    for _, a in anchors.iterrows():
        asig = _sig(a)
        block = blocks.get((asig["character"], asig["maker"]), [])
        hits = []
        for c in block:
            sc, reason = _score(asig, _sig(c))
            if REVIEW_MIN <= sc < AUTO_THRESHOLD:
                hits.append((sc, c, reason))
        if not hits:
            continue
        hits.sort(key=lambda x: -x[0])
        lines.append(f"\n### ANCHOR {a['source_item_id']} | {a.get('maker')} | "
                     f"{a.get('title_raw')}")
        for sc, c, reason in hits[:8]:
            lines.append(f"  ?{sc:.2f} {c['source']}:{c['source_item_id']} | "
                         f"{int(c.get('price_krw') or 0):,}원 | {reason} | "
                         f"{c.get('title_raw')}")
    path = os.path.join(out_dir, "group_review.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines[:limit * 10]))
    return path, len(lines)


def assign_to_group(conn, assignments, anchor_source=AMIAMI, method="manual:review"):
    """검수 패스 수동 매칭 일괄 적용.

    assignments: [(cand_source, cand_item_id, anchor_item_id, conf, reason), ...]
    앵커(amiami) 그룹이 없으면 앵커 행으로 생성하고 후보를 멤버로 붙인다.
    method=manual:review 는 _add_member protect 대상 → 이후 `run.py group`(auto 재계산)
    재실행에도 보존된다. auto:blocking 으로 잡혀있던 후보는 수동 매칭으로 승격(덮어쓰기).
    """
    df = load_latest_df()
    amiami = {r["source_item_id"]: r for _, r in df[df.source == anchor_source].iterrows()}
    n = 0
    for cs, cid, aid, conf, reason in assignments:
        a = amiami.get(aid)
        if a is None:
            print(f"[assign] 앵커 없음(최신 스냅샷에 amiami {aid} 부재) → skip")
            continue
        gid = _ensure_group(conn, anchor_source, aid, _sig(a), a.get("title_raw"))
        if _add_member(conn, cs, str(cid), gid, conf, method, reason):
            n += 1
    conn.commit()
    return n


def prune_conflicts(conn):
    """앵커 라인마커와 충돌하는 비검증 멤버를 listing_group·product_match 양쪽에서 제거.

    옛 seed 오매칭(예: 무비몬스터 앵커 그룹에 S.H.몬스터아츠·이치방쿠지 매물 혼입)을 청소.
    method='anchor'·'manual:review'(사람 검증)는 보존, auto/seed 만 대상.
    product_match 까지 지워야 다음 migrate_from_matches 재실행에도 부활하지 않음(durable).
    """
    df = load_latest_df()
    titles = {(r["source"], r["source_item_id"]): (r.get("title_raw") or "")
              for _, r in df.iterrows()}
    groups = conn.execute(
        "SELECT id, anchor_source, anchor_item_id, canonical FROM product_group"
    ).fetchall()
    removed = []
    for g in groups:
        atitle = g["canonical"] or titles.get(
            (g["anchor_source"], g["anchor_item_id"]), "")
        mems = conn.execute(
            "SELECT source, source_item_id, method FROM listing_group WHERE group_id=?",
            (g["id"],),
        ).fetchall()
        for m in mems:
            meth = m["method"] or ""
            if meth == "anchor" or meth.startswith("manual"):
                continue
            ctitle = titles.get((m["source"], m["source_item_id"]), "")
            if not _marker_conflict(atitle, ctitle):
                continue
            conn.execute(
                "DELETE FROM listing_group WHERE source=? AND source_item_id=? AND group_id=?",
                (m["source"], m["source_item_id"], g["id"]),
            )
            conn.execute(
                "DELETE FROM product_match WHERE used_source=? AND used_item_id=?",
                (m["source"], m["source_item_id"]),
            )
            removed.append((g["id"], m["source"], m["source_item_id"]))

    # product_match 직접 스캔: migrate 가드로 listing_group 엔 안 들어왔지만
    # 남아있는 충돌 행(고아)도 제거 → premium/pricing 오염 방지
    anchor_title = {r["source_item_id"]: (r.get("title_raw") or "")
                    for _, r in df[df.source == AMIAMI].iterrows()}
    for pm in conn.execute(
        "SELECT amiami_item_id, used_source, used_item_id FROM product_match"
    ).fetchall():
        atitle = anchor_title.get(pm["amiami_item_id"], "")
        ctitle = titles.get((pm["used_source"], pm["used_item_id"]), "")
        if atitle and _marker_conflict(atitle, ctitle):
            conn.execute(
                "DELETE FROM product_match WHERE amiami_item_id=? AND used_source=? AND used_item_id=?",
                (pm["amiami_item_id"], pm["used_source"], pm["used_item_id"]),
            )
            removed.append(("pm", pm["used_source"], pm["used_item_id"]))
    conn.commit()
    return removed


def regenerate_product_match(conn):
    """그룹 → product_match 역생성 (중고 매물만). 기존 premium/pricing/dashboard 호환."""
    # 이전 자동 역생성분만 제거(수동 product_match 보존)
    conn.execute("DELETE FROM product_match WHERE method LIKE 'group:auto%'")
    conn.commit()
    rows = conn.execute("""
        SELECT g.anchor_item_id AS aid, lg.source AS src, lg.source_item_id AS iid,
               lg.confidence AS conf, lg.reason AS reason, lg.method AS method
        FROM product_group g
        JOIN listing_group lg ON lg.group_id = g.id
        WHERE g.anchor_source = ? AND lg.source != ?
    """, (AMIAMI, AMIAMI)).fetchall()
    n = 0
    for r in rows:
        if r["src"] not in USED_SOURCES:
            continue            # 새↔새(naver 신품 등)는 product_match로 안 보냄(의미 보존)
        conn.execute(
            """INSERT OR REPLACE INTO product_match
               (amiami_item_id, used_source, used_item_id, confidence,
                reason, method, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (r["aid"], r["src"], r["iid"], r["conf"], r["reason"] or "",
             "group:" + (r["method"] or ""), _now()),
        )
        n += 1
    conn.commit()
    return n


def _counts(conn):
    g = conn.execute("SELECT COUNT(*) FROM product_group").fetchone()[0]
    m = conn.execute("SELECT COUNT(*) FROM listing_group").fetchone()[0]
    by = conn.execute(
        "SELECT method, COUNT(*) FROM listing_group GROUP BY method ORDER BY 2 DESC"
    ).fetchall()
    return g, m, by


def run():
    init_db()
    conn = get_conn()
    ng, nm = migrate_from_matches(conn)
    print(f"[group] 이관: product_match 앵커 {ng}건, 멤버 {nm}건")
    asg, amb = auto_block(conn)
    print(f"[group] 자동: {asg}건 그룹화, 모호 보류 {amb}건")
    pruned = prune_conflicts(conn)
    if pruned:
        print(f"[group] 라인충돌 정리: {len(pruned)}건 제거 {pruned}")
    path, nanchor = export_review(conn)
    print(f"[group] 검수 후보 {nanchor}개 앵커: {path}")
    npm = regenerate_product_match(conn)
    print(f"[group] product_match 역생성 {npm}건 (premium/pricing 호환)")
    g, m, by = _counts(conn)
    print(f"[group] 현재 product_group {g}개 / listing_group {m}건")
    for method, cnt in by:
        print(f"         - {method}: {cnt}")
    conn.close()


if __name__ == "__main__":
    run()
