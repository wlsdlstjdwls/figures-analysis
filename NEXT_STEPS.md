# 다음 작업 / 세션 인계 문서

> 최종 업데이트: 2026-06-24(3) · **반자동 상품그룹 매처 구축 세션: source 무관 상품그룹 일반화 + 자동 블로킹.** 매칭 30→**46건**(수동) + 자동 100건 그룹화.
> 새 세션에서 이 파일부터 읽으면 이어서 작업 가능. 전체 설계는 [PLAN.md](PLAN.md).

## 이번 세션 변경 (2026-06-24 #3) — 상품그룹 매처 + 대시보드 레이아웃

### ⭐ 핵심: 반자동 상품그룹 매처 신규 (`run.py group`)
- **동기**: 사용자가 "아무 상품이나 클릭 → 그 상품 시세비교(새↔새/중고↔중고/새↔중고)" 원함. 기존 `product_match`는 amiami 한 방향 앵커뿐 → 일반화 필요. naver 25k는 손매칭 불가 → 반자동 필요.
- **신규 테이블** (`storage/schema.sql`): `product_group`(source 무관 "같은 제품" 단위) + `listing_group`(매물→그룹 매핑). init_db가 자동 생성(IF NOT EXISTS).
- **신규 모듈** `normalize/grouping.py` + `run.py group` — 파이프라인:
  1. `migrate_from_matches` — 기존 product_match → 그룹 이관(멱등)
  2. `auto_block` — character+maker+연식(+라인/상/바코드) **고정밀 자동 그룹화**. 재실행 시 `auto:blocking`분만 삭제·재계산(수동/seed/anchor 보존)
  3. `export_review` — 자동임계(0.8) 미달·0.55↑ 후보를 `%TEMP%/figures_match/group_review.txt`로 덤프(검수용)
  4. `regenerate_product_match` — 그룹→product_match **역생성(중고 매물만)** → 기존 premium/pricing/dashboard 무수정 호환
- **정밀도 가드**(중요, `_score`): ① 묶음/일괄(`BUNDLE_TOKENS`) 제외 ② **라인마커 양성확인**(`LINE_MARKERS`) — 앵커가 무비몬스터면 후보도 무비몬스터 명시 必. 몬스터아츠/이치반쿠지/타마시/반프레스토/가챠/데포리얼 혼입 차단. (고질라2023처럼 character+maker+연식이 같아도 제품군 수십종인 케이스 방어)
- **결과**: 그룹 24개 / 멤버 168(자동100+이관44+앵커24), naver·bunjang·yahoo·amiami 교차. 상품단위 프리미엄 국내14+일본11종(이전 12+9). naver 신품도 묶임 → **새↔새 비교 토대 확보**(아직 화면 미노출).
- **새 사이트 추가 시**: `run.py group` 재실행만. 매칭 영구저장+수동분 보존+자동분만 갱신 → 전체 재작업 X.
- ⚠️ **상속 노이즈**: 옛 product_match seed 일부 오매칭(예 yahoo "モスラ幼虫 テストショット" 1.4M) 남아있음. 자동매처 산물 아님(자동은 정상 거부). seed 재검 필요.
- **수동 매칭 추가**: bunjang↔amiami 16건 직접 적재(가규라·제일복권 모스라/메카고질라·신가면라이더 A상·무비몬스터 1954/울티마 등) → 30→46.

### 대시보드 레이아웃 변경 (`report/html_report.py` + `reports/dashboard.html` 둘 다 패치)
- `.filters` 세로 배치: 검색창 한 줄 전체 → 아래 줄 `.ftools`(필터·정렬 + 보기토글) → **건수(`#cntTop`) 같은 줄 맨 오른쪽**(margin-left:auto). 건수는 chips바에서 빼고 `#cntTop`으로 이동.
- ⚠️ `dashboard.html`은 직접 패치했으나, 다음 `run.py html` 재생성 시 템플릿(.py 패치본)에서 다시 나옴(일관).

### 다음 세션 할일 (이 순서 권장)
1. **검수 패스로 매칭 키우기** (recall↑): `%TEMP%/figures_match/group_review.txt`(1,377앵커) 열어서 Claude가 같은제품 판정. 특히 **naver가 라인 미표기라 자동 탈락한 정상 매물** 다수. ⚠️ **선행작업**: `grouping.py`에 그룹용 수동 저장 헬퍼 추가 필요(현재 `llm_match.save_matches`는 product_match 전용. listing_group에 직접 넣고 anchor 그룹에 붙이는 `assign_to_group(source,item_id,anchor_item_id,conf,reason)` 같은 함수 만들 것). 저장 후 `regenerate_product_match` 재실행.
2. **비교 UI**: 카드 클릭 → 그룹 멤버를 새/중고·사이트별로 보여주는 모달. `html_report.py`에서 `product_group`+`listing_group` 조인해 `D.groups`(상품→멤버 가격리스트) 주입 후 카드 onclick 모달 렌더. 이게 사용자가 원한 "클릭→시세비교" 본체.
3. **옛 seed 노이즈 정리**: 상속 오매칭(테스트샷 등) 제거 또는 신뢰도 하향.
4. **자동화**: `run.py daily`에 `renormalize`+`group` 추가(매일 자동 재그룹). 단 자동화 변경은 사용자 확인 후.

## 이번 세션 변경 (2026-06-24 #2) — 고도화 ①②③④
- **① yahoo_jp 매칭 통합**: `JP_USED=(yahoo_jp)` 신설. `export_candidates`가 yahoo_jp 후보도 덤프(일본어라 `JP_KAIJU_TOKENS` 키워드 보완). amiami↔yahoo_jp 실제 매칭 19건 적재(GSC SSSS 소프비·MMS·이치방쿠지). product_match 11→30.
- **②/한일차익**: `pricing.py`에 일본 매입시세(yahoo_jp 실거래 중앙값) + `jp_margin_pct`(국내시세/일본매입). 예: DYNAZENON 가규라 일본 36,595 매입→국내 69,500 = **+90%**. `premium.py`는 `used_sources` 파라미터로 국내/일본 프리미엄 둘 다 산출(`compute_product_premium(used_sources=JP_USED)`).
- **③ 일본어 정규화**: `extract.py` CHARACTERS/GENRE_RULES에 일본어(ゴジラ·ウルトラマン·仮面ライダー·グリッドマン·怪獣8号 등) 보강. **신규 `run.py renormalize`** = 저장된 행 title_raw로 genre/character 소급 재계산. yahoo_jp 기타 **1628→3**(괴수1514·특촬299).
- **④ 대시보드**: 💹에 🇯🇵일본 프리미엄 카드(kind=일본), 💰에 일본매입→한일차익% 라인 추가. `run.py html` 재생성 완료.
- ⚠️ **국내 시세는 여전히 호가근거**(실거래근거 0). yahoo_jp(일본)는 매입참고로만 쓰고 국내 판매시세엔 안 섞음. 국내 실거래 비중↑ 하려면 **와이스 sold↔amiami 매칭** 필요(아래 0순위 ②).

## 현재 상태 (한눈에)

**데이터**: SQLite `data/figures.db` (gitignore 제외, 로컬 전용). 약 1.4만행.
- 소스별: 네이버 3,360 · 번개장터 881 · 아미아미 433 · 와이스 39 (상품별 최신 기준 ~4,700건)
- 모든 행 한 테이블 `product_listing`. `collected_at`로 스냅샷 누적 → 시계열 가능. 분석은 상품별 최신 1건.

**연동 완료 소스 (6)**:
| 소스 | 명령 | 방식 | 데이터 | 자동수집 |
|------|------|------|--------|----------|
| 네이버쇼핑 | `run.py collect` | 공식 API | 국내 새제품 호가 | daily |
| 와이스 | `run.py wyyyes` | 비공식 JSON API | **국내 낙찰가=실거래** + 진행중 경매 + 상세/상태 | daily + 3h 폴링 |
| 번개장터 | `run.py bunjang` | 비공식 API | 국내 중고 호가 + 등록일/지역 | daily |
| 아미아미 | `run.py amiami` | Playwright(CF우회) | **일본 정가 + 발매일 + JAN바코드** | 수동(주1회 권장) |
| 야후옥션JP | `run.py yahoo` | __NEXT_DATA__ JSON | **일본 중고 낙찰가=실거래** | 수동 |
| eBay | `run.py ebay` | 공식 API | 해외 호가 | ⏸ **키 발급 대기중** |

**자동화 (Windows 작업 스케줄러)**:
- `FiguresAnalysisDaily` — 매일 09:00, 전체 수집→리포트→HTML
- `FiguresWyyyesPoll` — 3시간마다, 와이스 낙찰가 누적
- ⚠️ PC 켜져 있어야 실행. 24시간 원하면 VPS.

**화면**: `reports/dashboard.html` (상품 카드 그리드). 검색·출처/구분/장르 필터·정렬(가격/날짜 최신·오래된순)·보기모드(갤러리/그리드/리스트)·모바일 반응형. 카드: **출처 색상뱃지**·이미지·가격·실거래/호가·상태·연식·**📅 날짜(발매/등록/거래, 라벨화)**·🏬매장·설명. 상단 **💹 프리미엄 섹션**(접이식). ⚠️ naver는 source_date 없음 → 날짜정렬 시 뒤로.

---

## 다음 할일 (우선순위)

### 0순위 ⭐ 판매가 추천 엔진 — v1 완료 (2026-06-24)
- 목적: "이 제품 내 숍에 얼마에 팔까?" 자동 산출. 핵심 비즈니스 기능.
- ✅ `analysis/pricing.py` · `run.py pricing` · 대시보드 💰 섹션:
  - **시세 = 국내 중고 실거래(와이스 낙찰) 중앙값**, 없으면 호가 폴백(basis 라벨 표시).
  - 추천가 2종: **빠른회전=시세×1.00 · 고점=시세×1.10** (상수 `FAST_MULT`/`TOP_MULT`).
  - 근거: 정가대비%·실거래n·호가n. 매칭(product_match) 있는 상품만.
- ⚠️ **현재 매칭 9건 전부 번개 호가 근거** (와이스 sold 매칭 0). 실거래 기반 추천 늘리려면 와이스 낙찰가↔아미아미 매칭 발굴 필요.
- ⚠️ **남은 작업**: ① 매입가 입력 기반 마진/수익 계산(선택) ② 와이스 sold 매칭 발굴 → basis=실거래 비중↑ ③ 사이트 확장 시 시세밴드 표본↑(아래 0.5순위).

### 0.5순위 ⭐ 사이트 확장 (시세 표본·커버리지) — 사용자 요청
- 목적: 시세밴드 표본↑ → 판매가/프리미엄 신뢰도↑. 국내+일본+해외.
- ✅ **야후옥션 재팬 완료 (2026-06-24)** — `collectors/scrape/yahoo_jp.py`, `run.py yahoo`.
  - **일본 중고 실거래(낙찰가)** 1,818행 수집. `source=yahoo_jp`, `is_sold=1`, currency JPY.
  - 기술: `closedsearch` 페이지가 Next.js → `__NEXT_DATA__` JSON에서 `initialState.search.items.listing.items[]` 추출. DOM파싱 불필요, 인증 불필요.
  - ⚠️ **호가(active) 미수집**: `search/search`는 Next.js 아님(__NEXT_DATA__ 없음) → 별도 DOM파서 필요, 후순위(국내 호가 이미 있음).
  - 🎯 **다음**: yahoo_jp(일본 실거래)↔amiami(정가)↔국내중고 매칭 = **매입원가 기반 마진 계산**(일본서 매입→국내 판매 차익). 한일차익(3순위)도 여기서 나옴.
- **남은 후보 (가치×난이도)**:
  - 🟢 **eBay**(해외 호가) — 코드 준비됨(`collectors/api/ebay.py`), **키 발급=사용자 작업**(PLAN §10.2). Claude는 키 못 만듦.
  - 🟡 **HLJ/BBTS**(새제품 정가 해외) — ⚠️ HLJ 가격이 JS 지연로딩(검색HTML엔 빈 placeholder) → 가격 AJAX 엔드포인트 정찰 필요.
  - 🔴 **메루카리 JP** — `api.mercari.jp` 400(DPoP 토큰 필요). 옵션: ① `mercapi`류 파이썬 라이브러리(DPoP 서명 생성) ② 주거용 프록시+스텔스브라우저+FlareSolverr ③ Apify 유료 Mercari Scraper. 전용 인프라 필요 → 보류.
  - 🔴 **국내 옥션/G마켓** — `browse.auction.co.kr` 403 차단. 헤더위장/세션 추가조사 필요.
  - 🔴 스루가야·만다라케·당근·중고나라 — CF/게이트/봇차단(아래 보류 참조).
- 권장 다음 순서: **yahoo_jp 매칭(매입가 마진) → eBay(키 나오면) → HLJ 가격API 정찰**.

### 1순위 ⭐ 프리미엄율 분석 — v1 완료(세그먼트 근사), 정밀화 남음
- 목적: "정가 대비 중고가 몇 % 프리미엄?" = 핵심 인사이트 (PLAN §5.1).
- ✅ **v1 완료** (`analysis/premium.py`, `run.py premium`, 대시보드 💹 프리미엄 섹션):
  - **character(×maker) 세그먼트 단위** 근사. IQR 이상치 제거 후 `중고中/정가中`.
  - 현재 결과: 가면라이더 495% · 울트라맨 188% · 고질라 63% (겹치는 캐릭터 3개뿐).
  - 대시보드: 상단 접이식 섹션, 세그먼트 카드(프리미엄%·정가→중고·표본수).
- ✅ **v2 완료 (Claude Code 직접 매칭, 유료 API 미사용)** — `normalize/llm_match.py`, `run.py match`, `product_match` 테이블, `analysis/premium.py` 상품단위 계산:
  - 워크플로: `export_candidates()`가 겹치는 genre(괴수/특촬/공룡/괴물) 아미아미 정가상품·국내 중고 후보를 UTF-8 덤프 → **Claude Code(세션 내 나)가 두 파일 읽고 같은제품 판정** → `save_matches([...])` 적재. ⚠️ ANTHROPIC API 안 씀(사용자 방침).
  - `premium.py`: 매칭 있으면 **상품단위** 우선 출력, 없으면 세그먼트 근사 폴백.
- ✅ **수집 검색어 한일 정렬 (2026-06-24)** — 양쪽에 공통 라인 추가(naver/bunjang/amiami QUERIES, `# KEEP IN SYNC` 주석). 신규 라인이 genre로 잡히게 `normalize/extract.py` 사전 보강(괴수8호·그리드맨·다이나제논·가규라). amiami 수집기 견고화(쿼리별 fetch try/except로 1건 실패가 전체 안 죽임).
  - 수집 결과: 무비몬스터 고질라 앵커 다수 확보(amiami +185행, MMS 고질라 133·이치방쿠지 고질라/라이더 32) + 국내 무비몬스터/제일복권/이치방쿠지 매물.
- ✅ **상품매칭 9건 (was 1)** — MMS 고질라·이치방쿠지·X-Plus. premium 상품단위:
  - FSL 고질라2001 188% · 토호 고질라2019 165% · 고질라 울티마 S.P 163% · 이치방쿠지 메카고질라1993(A상) 147% · 데스토로이아 128% · DYNAZENON 가규라 123% · 버닝고질라 114% · 토호30cm 고질라2016 4형태각성 92% · 고질라(1954) 57%.
- ✅ **대시보드 💹 연결 완료** (`report/html_report.py`): 상품단위(LLM 매칭, 초록 "상품" 뱃지) + 세그먼트 근사(보라 "세그먼트" 뱃지) 두 종 카드. `run.py html` 재생성. compute_product_premium 사용.
- ⚠️ **amiami CF 피로 / 미수집 라인**: 한 세션 다량 쿼리 시 후반 `Failed to fetch`. **소량 배치(쿼리 2개)로 collect 호출** 분리하면 fresh 브라우저로 회피됨(이번에 x-plus 100행 확보). 단 `kaiju no.8 sofubi`·`SSSS.DYNAZENON sofubi`·`godzilla minus one sofubi`는 amiami 검색결과 0건(해당 라인 미취급/명칭 다름) → 그쪽 매칭은 불가, 다른 키워드 탐색 필요.
- ⚠️ **남은 작업**: ① 매칭 더 발굴(특촬/울트라맨 빅소프비 등 미검토 영역, `run.py match` 덤프 재검토) ② 매칭 confidence 검수 ③ 매칭 늘면 한일가격차·호가/실거래 괴리(3순위) 따라옴.

### 2순위 eBay 합류 (키 나오면)
- 코드 준비됨(`collectors/api/ebay.py`). `.env`에 `EBAY_APP_ID`/`EBAY_CERT_ID` 넣고 `run.py ebay`.
- 발급 절차 PLAN §10.2. Browse=호가. 해외 빈티지 괴수 세그먼트.

### 3순위 한일 가격차 / 호가-실거래 괴리 분석
- 한일: 동일제품 price_krw 비교(아미아미 일본 vs 네이버/번개 국내) → 직구차익.
- 괴리: 와이스 호가(active) vs 낙찰가(sold) 비교.
- 둘 다 매칭 필요 → 1순위 매칭 로직 완성 후 자연히 따라옴.

### 4순위 시계열 (며칠 누적 후)
- 스냅샷 며칠 쌓이면 `run.py timeseries`. 현재 1일치라 아직 무의미.

### 보류 (인프라 필요)
- **만다라케**: 지역선택 splash 게이트. EN클릭→본사 튕김. 지역쿠키 우회 추가조사 필요.
- **스루가야**: 아미아미보다 강한 Cloudflare("Just a moment"). stealth 브라우저/레지덴셜 프록시 필요.
- **당근/중고나라**: 강한 봇차단·인증. Phase3, 전용 인프라.

---

## 기술 메모 (재현용)
- **아미아미 CF 우회**: 평범한 requests는 TLS핑거프린트로 403. Playwright로 `amiami.com` 로드 후 **페이지 컨텍스트 fetch**로 `api.amiami.com/api/v1.0/items?s_keywords=<kw>&lang=eng&pagecnt=&pagemax=` 호출(헤더 `X-User-Key: amiami_dev`). 검색param=`s_keywords`(복수형).
- **와이스 API**: `wyyyes.com/r0.app/discovery/auctionHistoryFeed?category=figure`(낙찰), `auctions/v2`(진행중), 상세 `r0.app/stocks/<id>`. 인증 불필요.
- **번개 API**: `api.bunjang.co.kr/api/1/find_v2.json?q=&page=&n=100`. 인증 불필요.
- **DB 마이그레이션**: `storage/db.py init_db()`가 ALTER로 컬럼 자동 추가. 새 컬럼은 거기에.
- **중복 제거**: 분석/대시보드는 `storage.db.load_latest_df()` (상품별 최신 스냅샷 1건).

## 빠른 시작 (새 세션)
```
python run.py daily        # 전체 수집 + 리포트 + HTML
python run.py amiami       # 아미아미만 (Playwright)
python run.py match        # 매칭 후보 덤프 (Claude Code가 판정 → save_matches)
python run.py renormalize  # extract 사전 보강 후 기존행 genre/character 소급 재계산
python run.py premium      # 국내+일본 프리미엄
python run.py pricing      # 판매가 추천 + 한일차익
start reports/dashboard.html
```
