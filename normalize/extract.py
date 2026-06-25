"""상품명 -> 구조화 필드 (룰 기반, Phase1).

대상: 소프비(soft vinyl) 피규어. 괴수/공룡/특촬 중심 + 기타.
네이버 제목은 띄어쓰기가 불규칙("울트라 맨") → 공백 제거 후 매칭한다.
Phase2에서 LLM(Claude) 추출로 보강.
"""
import re

# ── 제조사 사전 (소프비 브랜드) ──────────────────────────────
MAKERS = {
    "반다이": "Bandai", "bandai": "Bandai",
    "엑스플러스": "X-Plus", "x-plus": "X-Plus", "xplus": "X-Plus", "x플러스": "X-Plus",
    "마미트": "Marmit", "marmit": "Marmit",
    "메디콤": "Medicom", "메디컴": "Medicom", "medicom": "Medicom", "vag": "Medicom",
    "카이요도": "Kaiyodo", "kaiyodo": "Kaiyodo",
    "ccp": "CCP",
    "m1호": "M1go", "m1go": "M1go",
    "불마크": "Bullmark", "bullmark": "Bullmark",
    "유타카": "Yutaka", "yutaka": "Yutaka",
    "포피": "Popy", "popy": "Popy",
    "마루산": "Marusan", "marusan": "Marusan",
    "반프레스토": "Banpresto", "banpresto": "Banpresto", "밴프레스트": "Banpresto",
    "타카라토미": "TakaraTomy", "타카라": "TakaraTomy",
    "엔스카이": "Ensky",
}

# ── 시리즈/라인 사전 ─────────────────────────────────────────
LINES = {
    "무비몬스터": "Movie Monster Series",
    "moviemonster": "Movie Monster Series",
    "울트라괴수": "Ultra Kaiju Series",
    "ultrakaiju": "Ultra Kaiju Series",
    "울트라소프비": "Ultra Sofubi Series",
    "소프비혼": "Sofvi Spirits",
    "메가소프비": "Mega Sofubi",
    "소프비": "Sofubi", "sofubi": "Sofubi", "sofvi": "Sofubi",
    "소프트비닐": "Sofubi",
}

# ── 캐릭터/IP 사전 ───────────────────────────────────────────
CHARACTERS = {
    # ── 고질라 유니버스 조연/빌런 괴수 — 프랜차이즈명(고질라)이 제목에 함께 박혀도
    #    실제 피규어 주인공이 이쪽이면 collapse 되지 않게 ゴジラ보다 먼저 둔다.
    #    (예: "Battra Larva ... Godzilla Movie Monster Series" → Battra)
    "메카니콩": "Mechani-Kong", "mechanikong": "Mechani-Kong",      # 'kong' 포함 → 킹콩보다 먼저
    "메카고질라": "Mechagodzilla", "メカゴジラ": "Mechagodzilla", "mechagodzilla": "Mechagodzilla",
    "킹기도라": "King Ghidorah", "기도라": "King Ghidorah",
    "キングギドラ": "King Ghidorah", "ギドラ": "King Ghidorah",
    "ghidorah": "King Ghidorah", "ghidora": "King Ghidorah",   # 'King Ghidora' 철자변형
    "kingghidora": "King Ghidorah", "ghidrah": "King Ghidorah",
    "스페이스고질라": "Space Godzilla", "スペースゴジラ": "Space Godzilla", "spacegodzilla": "Space Godzilla",
    "고질라주니어": "Godzilla Junior", "godzillajr": "Godzilla Junior", "ゴジラジュニア": "Godzilla Junior",
    "리틀고질라": "Little Godzilla", "littlegodzilla": "Little Godzilla", "リトルゴジラ": "Little Godzilla",
    "미니라": "Minilla", "minilla": "Minilla", "ミニラ": "Minilla", "minya": "Minilla",
    "바트라": "Battra", "밧트라": "Battra", "배트라": "Battra", "battra": "Battra", "バトラ": "Battra",
    "데스토로이아": "Destoroyah", "데스토로이야": "Destoroyah", "destoroyah": "Destoroyah",
    "destroyah": "Destoroyah", "デストロイア": "Destoroyah",
    "디스트로이어": "Destoroyah", "디스트로이아": "Destoroyah",   # Destroyer 음차 변형
    "비오란테": "Biollante", "biollante": "Biollante", "ビオランテ": "Biollante",
    "앙기라스": "Anguirus", "안기라스": "Anguirus", "anguirus": "Anguirus", "アンギラス": "Anguirus",
    "헤도라": "Hedorah", "hedorah": "Hedorah", "ヘドラ": "Hedorah",
    "가이간": "Gigan", "gigan": "Gigan", "ガイガン": "Gigan",
    "메가로": "Megalon", "메가론": "Megalon", "megalon": "Megalon", "メガロ": "Megalon",
    "에비라": "Ebirah", "ebirah": "Ebirah", "エビラ": "Ebirah",
    "바라곤": "Baragon", "baragon": "Baragon", "バラゴン": "Baragon",
    "라돈": "Rodan", "로단": "Rodan", "rodan": "Rodan", "ラドン": "Rodan",
    "제트재규어": "Jet Jaguar", "jetjaguar": "Jet Jaguar", "ジェットジャガー": "Jet Jaguar",
    "킹콩": "King Kong", "kingkong": "King Kong", "コング": "King Kong", "kong": "King Kong",
    "고질라": "Godzilla", "godzilla": "Godzilla", "ゴジラ": "Godzilla", "고지라": "Godzilla",
    "울트라맨": "Ultraman", "ultraman": "Ultraman", "ウルトラマン": "Ultraman",
    # ── 가메라 유니버스 조연/빌런 — 가메라보다 먼저 ──
    "갸오스": "Gyaos", "gyaos": "Gyaos", "ギャオス": "Gyaos",
    "바루곤": "Barugon", "barugon": "Barugon", "バルゴン": "Barugon",
    "기롱": "Guiron", "guiron": "Guiron", "ギロン": "Guiron",
    "이리스": "Iris", "irys": "Iris", "イリス": "Iris",
    "레기온": "Legion", "legion": "Legion", "レギオン": "Legion",
    "가메라": "Gamera", "gamera": "Gamera", "ガメラ": "Gamera",
    "가면라이더": "Kamen Rider", "kamenrider": "Kamen Rider", "仮面ライダー": "Kamen Rider",
    "발탄성인": "Baltan", "발탄": "Baltan", "バルタン": "Baltan",
    "제튼": "Zetton", "ゼットン": "Zetton",
    "고모라": "Gomora", "ゴモラ": "Gomora",
    "레드킹": "Red King", "レッドキング": "Red King",
    "모스라": "Mothra", "mothra": "Mothra", "モスラ": "Mothra",
    # 현행 신품 라인 (한일 겹침 노림 — 양쪽 수집 검색어 정렬용)
    "괴수8호": "Kaiju No.8", "카이주8호": "Kaiju No.8", "kaijuno8": "Kaiju No.8",
    "kaijuno.8": "Kaiju No.8", "kaiju8": "Kaiju No.8",
    "怪獣8号": "Kaiju No.8", "怪獣８号": "Kaiju No.8",
    "그리드맨": "Gridman", "gridman": "Gridman", "グリッドマン": "Gridman",
    "다이나제논": "Dynazenon", "dynazenon": "Dynazenon", "ダイナゼノン": "Dynazenon",
    "가규라": "Gagula", "gagula": "Gagula", "ガギュラ": "Gagula",
    "공룡": "Dinosaur", "다이노": "Dinosaur", "티라노": "Tyrannosaurus", "恐竜": "Dinosaur",
    "쥬라기": "Jurassic", "jurassic": "Jurassic",
}

# ── 장르 분류 (우선순위 순서) ────────────────────────────────
GENRE_RULES = [
    ("괴수", ["고질라", "godzilla", "고지라", "가메라", "gamera", "킹기도라", "기도라",
              "모스라", "mothra", "메카고질라", "괴수", "kaiju", "발탄", "제튼",
              "고모라", "레드킹", "데스토로이아", "데스토로이야",
              "괴수8호", "카이주8", "kaiju8", "kaijuno8", "kaijuno.8",
              "그리드맨", "gridman", "다이나제논", "dynazenon", "가규라", "gagula",
              # 고질라/가메라 조연·빌런 괴수
              "킹콩", "kingkong", "kong", "바트라", "battra", "갸오스", "gyaos",
              "비오란테", "biollante", "라돈", "rodan", "앙기라스", "anguirus",
              "헤도라", "hedorah", "가이간", "gigan", "메가로", "megalon",
              "바라곤", "baragon", "에비라", "ebirah", "바루곤", "barugon",
              "고질라주니어", "godzillajr", "미니라", "minilla",
              # 일본어
              "ゴジラ", "怪獣", "ガメラ", "キングギドラ", "ギドラ", "モスラ",
              "メカゴジラ", "バルタン", "ゼットン", "ゴモラ", "レッドキング",
              "グリッドマン", "ダイナゼノン", "ガギュラ", "怪獣8号", "怪獣８号",
              "東宝", "デストロイア", "コング", "バトラ", "ギャオス", "ラドン"]),
    ("공룡", ["공룡", "다이노", "티라노", "dinosaur", "dino", "rex", "tyranno",
              "쥬라기", "jurassic", "트리케라", "恐竜"]),
    ("특촬", ["울트라맨", "ultraman", "가면라이더", "kamenrider", "라이더",
              "특촬", "전대", "sentai", "히어로", "바이오맨", "체인지맨", "전격전대",
              "울트라소프비", "울트라빅", "울트라",
              # 일본어
              "ウルトラマン", "ウルトラ", "仮面ライダー", "ライダー", "円谷",
              "特撮", "電光超人", "戦隊"]),
    ("괴물", ["괴물", "monster", "몬스터", "크리쳐", "creature", "モンスター"]),
]

# ── 노이즈(비-피규어) 키워드 ─────────────────────────────────
NOISE_KW = [
    "케이스", "거치대", "스탠드", "받침", "도료", "물감", "파츠", "부품", "키트도료",
    "티셔츠", "후드", "의류", "키링", "키체인", "스티커", "뱃지", "에코백",
    "쿠션", "베개", "포스터", "엽서", "카드", "북마크", "마우스패드",
    "보호", "디스플레이장", "진열장", "아크릴케이스", "정리함",
]

SCALE_RE = re.compile(r"1\s*/\s*(\d+)")


def _despace(s):
    return s.replace(" ", "")


def _match_dict(text_nospace, d):
    for k, v in d.items():
        if _despace(k) in text_nospace:
            return v
    return None


def detect_genre(text_nospace):
    for genre, kws in GENRE_RULES:
        for kw in kws:
            if _despace(kw) in text_nospace:
                return genre
    return "기타"


def is_noise(text_nospace):
    return any(_despace(kw) in text_nospace for kw in NOISE_KW)


def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()


def extract_fields(title_raw):
    title = strip_html(title_raw)
    low = title.lower()
    nos = _despace(low)

    maker = _match_dict(nos, MAKERS)
    line = _match_dict(nos, LINES)
    character = _match_dict(nos, CHARACTERS)
    genre = detect_genre(nos)

    scale = None
    m = SCALE_RE.search(low)
    if m:
        scale = f"1/{m.group(1)}"

    condition = "used" if ("중고" in low or "used" in low) else "new"

    return {
        "title": title,
        "maker": maker,
        "line": line,
        "character": character,
        "genre": genre,
        "scale": scale,
        "condition": condition,
        "is_noise": 1 if is_noise(nos) else 0,
    }


def renormalize():
    """저장된 모든 행의 title_raw로 character/genre/maker/line/is_noise 재계산·UPDATE.

    extract 사전을 보강한 뒤 기존 데이터에 소급 적용할 때 사용
    (collect 안 거치고 분류만 갱신). 가격/날짜 등 원천 필드는 건드리지 않음.
      python run.py renormalize
    """
    from storage.db import get_conn
    conn = get_conn()
    rows = conn.execute("SELECT id, title_raw FROM product_listing").fetchall()
    changed = 0
    for rid, title_raw in rows:
        f = extract_fields(title_raw or "")
        cur = conn.execute(
            """UPDATE product_listing
               SET character=?, genre=?, maker=COALESCE(?, maker),
                   line=COALESCE(?, line), is_noise=?
               WHERE id=? AND (genre IS NOT ? OR character IS NOT ?)""",
            (f["character"], f["genre"], f["maker"], f["line"], f["is_noise"],
             rid, f["genre"], f["character"]),
        )
        changed += cur.rowcount
    conn.commit()
    conn.close()
    print(f"[renormalize] {len(rows)}행 검사, {changed}행 갱신.")
