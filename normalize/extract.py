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
    "고질라": "Godzilla", "godzilla": "Godzilla", "ゴジラ": "Godzilla", "고지라": "Godzilla",
    "울트라맨": "Ultraman", "ultraman": "Ultraman",
    "가메라": "Gamera", "gamera": "Gamera",
    "가면라이더": "Kamen Rider", "kamenrider": "Kamen Rider",
    "발탄성인": "Baltan", "발탄": "Baltan",
    "제튼": "Zetton",
    "고모라": "Gomora",
    "레드킹": "Red King",
    "킹기도라": "King Ghidorah", "기도라": "King Ghidorah",
    "모스라": "Mothra", "mothra": "Mothra",
    "메카고질라": "Mechagodzilla",
    "공룡": "Dinosaur", "다이노": "Dinosaur", "티라노": "Tyrannosaurus",
    "쥬라기": "Jurassic", "jurassic": "Jurassic",
}

# ── 장르 분류 (우선순위 순서) ────────────────────────────────
GENRE_RULES = [
    ("괴수", ["고질라", "godzilla", "고지라", "가메라", "gamera", "킹기도라", "기도라",
              "모스라", "mothra", "메카고질라", "괴수", "kaiju", "발탄", "제튼",
              "고모라", "레드킹", "데스토로이아", "데스토로이야"]),
    ("공룡", ["공룡", "다이노", "티라노", "dinosaur", "dino", "rex", "tyranno",
              "쥬라기", "jurassic", "트리케라"]),
    ("특촬", ["울트라맨", "ultraman", "가면라이더", "kamenrider", "라이더",
              "특촬", "전대", "sentai", "히어로", "바이오맨", "체인지맨", "전격전대",
              "울트라소프비", "울트라빅", "울트라"]),
    ("괴물", ["괴물", "monster", "몬스터", "크리쳐", "creature"]),
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
