# 다음 작업 / 세션 인계 문서

> 최종 업데이트: 2026-06-24(6) · **Hobby Search + Entertainment Earth 추가**(FlareSolverr 경유, 일본/미국 정가). 가동 12소스 + 라쿠텐 보류.
> 새 세션에서 이 파일부터 읽으면 이어서 작업 가능. 전체 설계는 [PLAN.md](PLAN.md).

## 이번 세션 변경 (2026-06-24 #6) — Hobby Search + Entertainment Earth (FlareSolverr)

### ⭐ 신규 소스 2종 (FlareSolverr 경유, suruga와 동일 CF 우회 인프라)
- 정찰: HS·EE 둘 다 **전사 Cloudflare("Just a moment")** → 평범 requests 불가. FlareSolverr(`POST /v1 request.get`)로 CF 통과 확인(stillCF=False) 후 구현.
- **Hobby Search**(`run.py hobbysearch`, `collectors/scrape/hobbysearch.py`): 일본 영문몰 새제품 **정가**(JPY). HLJ/amiami 보완.
  - 검색 param=`searchkey`(stk 아님!) + `cat=figure`로 피규어 한정. 카드 `c-card`: `itemcode="(\d+)"`·`c-card__title`·`c-card__price-element>…JPY`·`c-card__maker`(=발매일)·img `/itbigNN/<code>.jpg`. ⚠️ SVG lottie 노이즈 → `_parse`가 `<svg>` 선제거.
  - 결과: **263고유행**(532수집dedup) 전부 가격+환율. 특촬112·괴수81·기타68(넨도/플라모 캐릭터). condition new, is_sold 0. source_date=발매일 문자열. 영문 키워드(godzilla/ultraman/kamen rider/gridman/kaiju no.8…).
- **Entertainment Earth**(`run.py entearth`, `collectors/scrape/entearth.py`): 미국 새제품 **정가**(USD). BBTS 보완.
  - 검색 param=`query1`(query 아님!). 카드 `.product product-hover` 안 `<button class="add-to-cart" data-*>`에 구조화 데이터: **data-sku·data-price(USD)·data-name·data-company(메이커)·data-theme·data-character**. 매우 깔끔.
  - 결과: **301고유행**(433수집dedup) 전부 가격. 괴수185·공룡65·특촬39. maker 잘 추출(Playmates/Hiya/Bandai Tamashii/Rokimoto). USD→price_krw fx보정. condition new, is_sold 0.
- 배선: 각 단독 명령 + **weekly 편입**(amiami/hlj/bbts/suruga/**hobbysearch/entearth**/rakuten). FlareSolverr 없으면 헬스체크 후 중단(무해). 대시보드 SOURCE_KO/COLOR: hobbysearch(주황#ff8800)·entearth(보라#6a3d9a). `run.py html` 재생성 13,674건.
- 🎯 다음: `run.py group` 재실행 시 자동블로킹 합류. ⚠️ HS 기타68 renormalize 대상.

## 이번 세션 변경 (2026-06-24 #5b) — 다나와 추가 (라쿠텐 키 막혀 전환)

### ⚠️ 라쿠텐 보류 — 일본 휴대폰 인증 장벽
- 라쿠텐 Web Service applicationId 발급 = 楽天会員 가입 필요 → **일본 휴대폰(080…) 인증 필수, 한국번호 불가**. eBay처럼 단순 키발급이 아님.
- 코드(`collectors/api/rakuten.py`)·배선·대시보드 등록은 **그대로 유지**(지인/일본번호/프록시 생기면 `.env RAKUTEN_APP_ID`만 넣으면 즉시 가동). weekly에서 키없으면 skip(무해).

### ⭐ 신규 소스 다나와 (`run.py danawa`) — 국내 가격비교 최저가 호가(KRW)
- `collectors/scrape/danawa.py`. **평범한 requests**(CF/인증 불필요, Hobby Search·Entertainment Earth는 전사 CF라 탈락 / 라쿠텐·이치바HTML은 Akamai차단).
- **파싱**: `search.danawa.com/dsearch.php?k1=<kw>&module=goods` HTML → `<li class="prod_item" id="productItem<cmpny>_<prod>">` 단위 분할(`_ITEM_RE`). 이름 `prod_name`(<b>제거), 최저가 첫 `price_sect <strong>…원`, go_link_goods.php 링크, img. 이름 접두어 `[중고]`→condition used, `[해외]`=직구(new). is_sold=0(판매 호가). currency KRW(=price_krw).
- **결과**: 602고유행(724수집·dedup), 전부 가격, 중고24. 장르 괴수271·특촬204·공룡14·기타106. 가격대 정상. CCP·카이요도·반다이 등 소프비 잘 잡힘.
- 배선: `run.py danawa` 단독 + **daily 편입**(naver/wyyyes/bunjang/yahoo/**danawa**, 가벼운 requests라 daily OK). 대시보드 SOURCE_KO/COLOR에 danawa(청록#00aab5) 등록. `run.py html` 재생성 확인.
- 🎯 **다음**: 네이버(국내 새제품 호가)와 danawa(최저가 비교) 둘 다 국내 신품 → 매물 풍부. `run.py group` 재실행 시 자동블로킹 합류. ⚠️ 기타106 = renormalize 대상(extract 사전 보강 후 `run.py renormalize`).

## 이번 세션 변경 (2026-06-24 #5) — 라쿠텐 이치바 추가

### ⭐ 신규 소스 라쿠텐 (`run.py rakuten`) — 일본 신품/중고 호가(JPY)
- `collectors/api/rakuten.py`. **공식 Rakuten Ichiba Item Search API**(가벼운 requests, CF/Playwright 불필요).
  - 엔드포인트 `app.rakuten.co.jp/services/api/IchibaItem/Search/20220601`, params `applicationId·keyword·format=json·hits(≤30)·page·sort=standard`.
  - 응답 `Items[]` 평탄구조(20220601). `itemName·itemPrice(JPY)·itemUrl·itemCode·shopName·mediumImageUrls(문자열 리스트)·genreId`. 구버전 `{Item:{...}}`·dict 이미지도 방어(`_unwrap`/`_image`).
  - 저장: `source=rakuten`, currency JPY, price_krw=fx보정(amiami/yahoo/hlj 동일단위), **is_sold=0(점포 호가)**, condition=extract 추정(中古 점포 섞임). 발매일 없음.
- ⚠️ **무료 applicationId 키 필요**(eBay와 동일 패턴, 단 **즉시발급·무심사**). 검색 페이지 HTML은 Akamai 차단(`Reference #...`)이라 스크랩 불가 → API만 길.
  - 발급: https://webservice.rakuten.co.jp/ 앱등록 → `.env`에 `RAKUTEN_APP_ID=<id>`.
- 배선: `run.py rakuten` 단독 + **weekly 편입**(amiami/hlj/bbts/suruga/**rakuten** → group 합류). 키 없으면 쿼리별 try/except로 skip(0 rows, 전체 안 죽음). 검증: 키 미설정 상태 `python run.py rakuten` EXIT=0 정상.
- 대시보드 SOURCE_KO/COLOR에 rakuten(진빨강#bf0000) 등록.
- 🎯 **다음**: 키 발급 후 `python run.py rakuten` → `run.py group` 재실행하면 자동블로킹 합류. 야후옥션(낙찰=실거래)과 라쿠텐(점포 호가) = 일본 호가/실거래 괴리 분석 표본.

## 이번 세션 변경 (2026-06-24 #4b) — FlareSolverr 인프라 + 스루가야

### ⭐ FlareSolverr 도입 (강한 Cloudflare 우회 인프라)
- **동기**: 스루가야 CF managed challenge가 headless/headed/stealth Playwright 다 미통과. 사용자가 인프라 도입 선택.
- **셋업**: Docker `ghcr.io/flaresolverr/flaresolverr:latest`, 포트 8191, `--restart unless-stopped`.
  ```
  docker run -d --name flaresolverr -p 8191:8191 -e LOG_LEVEL=info --restart unless-stopped ghcr.io/flaresolverr/flaresolverr:latest
  ```
- **사용법**: `POST http://localhost:8191/v1` `{cmd:"request.get", url, maxTimeout}` → `solution.response`에 CF 풀린 HTML. 환경변수 `FLARESOLVERR_URL`로 주소 변경 가능.
- ⚠️ Docker Desktop 켜져 있어야 함. weekly 자동수집의 suruga 단계가 이걸 의존(없으면 헬스체크 후 skip).

### ⭐ 신규 소스 스루가야 (`run.py suruga`) — 일본 중고/재고 정찰가
- `collectors/scrape/suruga.py`. FlareSolverr 경유. yahoo_jp(낙찰=실거래) 보완 = 일본 중고 **고정가 매장 정찰가**.
- **파싱**: 검색카드 `<div class="photo_box">` 단위 분할 → product/detail/<id> + h3.product-name(풀제목) + .condition(상품타입) + .brand(메이커JP). **가격은 페이지 GTM JS `item_product.price`(정수 JPY)를 item_id로 매핑**(DOM 가격표기는 배송표/타임세일 섞여 지저분).
- **결과**: 363행, 347 가격. 괴수281·특촬78. condition=used 고정(스루가야 중고위주), is_sold=0(매장 호가). ⚠️ 일부 비피규어(캐릭터카드·플레이매트) 혼입. ⚠️ maker가 일본어(バンダイ) → 영문 소스(amiami/bbts)와 maker 매칭 시 불일치 주의.
- weekly에 편입(amiami/hlj/bbts/**suruga**).
- 대시보드 SOURCE_KO/COLOR에 suruga(보라#7b2ff7) 등록.

## 이번 세션 변경 (2026-06-24 #4) — 사이트 추가(HLJ·BBTS) + 자동수집 분리

### ⭐ 자동수집 daily/weekly 분리 (사용자 승인)
- **동기**: 호가/실거래는 매일 변동(시계열 가치) vs 정가는 거의 불변+Playwright/CF 무거움 → 같은 daily에 섞으면 CF로 daily 전체 지연/멈춤 위험.
- **`run.py daily`** (매일 09시 `FiguresAnalysisDaily`, 20시 `FiguresAnalysis_Daily`): naver+wyyyes+bunjang+**yahoo(신규 편입)** → report+html. yahoo는 requests라 가벼워 daily OK.
- **`run.py weekly`** (신규, 일요일 10시 `FiguresWeekly`+`run_weekly.bat`): fx→**amiami+hlj+bbts**(정가)→`group`(재블로킹)→premium+pricing→html. 전부 try/except로 1개 실패가 전체 안 죽임.
- ⚠️ `FiguresAnalysisDaily`(09시)+`FiguresAnalysis_Daily`(20시) **둘 다 run_daily.bat** — 1일2회(중복인지 의도인지 불명, 삭제 안 함). snapshot 누적이라 무해.

### ⭐ 신규 소스 BBTS (`run.py bbts`) — 미국 새제품 정가(USD)
- `collectors/scrape/bbts.py`. Cloudflare challenge(amiami와 동일) → Playwright. 검색결과 서버렌더 `.product-card` DOM → 페이지 컨텍스트 `evaluate`로 파싱(XHR API 없음).
- 카드: href(/product/...-<code>), title, company("By:<maker>"), price("PRE-ORDER\\n$129.99"), img. USD→price_krw fx보정. condition new, is_sold 0.
- ⚠️ **CF 피로 회피 = 쿼리마다 fresh context**(한 컨텍스트 다량탐색 시 2~3페이지 후 challenge 안풀림). 페이지당 20건, 쿼리당 최대 40건(page3은 challenge로 보통 0).
- **결과**: 152고유행. 전부 가격. 괴수110·특촬34. maker Bandai/Hiya/threezero/McFarlane/Funko 등 잘 추출.
- 대시보드 SOURCE_KO/COLOR에 bbts(빨강#d62828) 등록.

## 이번 세션 변경 (2026-06-24 #4a) — HLJ 사이트 추가

### ⭐ 신규 소스 HLJ (`run.py hlj`) — 해외(일본발) 새제품 정가
- **동기**: 0.5순위 사이트확장. 시세밴드 표본↑. eBay는 키 막힘 → 🟡 HLJ 우선.
- **2단계 수집** (`collectors/scrape/hlj.py`, 평범한 requests.Session, CF/인증 불필요):
  1. `search/?Word=<kw>&Page=<n>` HTML → 카드 정규식(`_CARD_RE`)으로 item_code·이름·url·이미지 + csrf토큰(`_CSRF_RE`). 24건/페이지.
  2. `search/livePrice/?item_codes=<csv>&csrfmiddlewaretoken=<tok>` JSON(배치) → **JPYprice(정가 엔)**·release_date·stockStatusCode. (가격이 검색HTML엔 없고 JS 지연로딩 — NEXT_STEPS에 적힌 그 AJAX 엔드포인트가 livePrice였음.)
- 저장: `source=hlj`, currency JPY(JPYprice), price_krw=fx보정(amiami/yahoo와 동일단위), condition new, is_sold 0. source_date=발매(예정)일 문자열("August 2026"). 제목 `html.unescape`.
- **결과**: 571고유행(586수집·dedup). 전부 가격+환율보정. 노이즈 0. 장르 괴수454·특촬89·괴물18·기타10. 가격 JPY 350~227,900(평균7,789).
- 대시보드: `html_report.py` SOURCE_KO/SOURCE_COLOR에 hlj(파랑#1f6feb)+yahoo_jp(빨강) 등록. `run.py html` 재생성, 카드 노출 확인.
- **수동수집 유지**(amiami/yahoo처럼). 정가 자주 안 바뀜 → daily 미편입. 자동화 원하면 사용자 확인 후 daily에 추가.

### 다음 후보
- **HLJ↔amiami↔국내 매칭**: HLJ도 일본 정가 → `run.py group` 재실행하면 자동블로킹에 합류(character+maker+연식). 단 HLJ는 maker 추출 약함(`maker=None` 다수, 라인명이 제목 앞 "Series:"형) → grouping 정밀도 영향 점검 필요.
- 매칭확대(#1)·비교UI(#2)는 여전히 미착수(사용자 핵심요구).

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

**연동 완료 소스 (9)**:
| 소스 | 명령 | 방식 | 데이터 | 자동수집 |
|------|------|------|--------|----------|
| 네이버쇼핑 | `run.py collect` | 공식 API | 국내 새제품 호가 | daily |
| 와이스 | `run.py wyyyes` | 비공식 JSON API | **국내 낙찰가=실거래** + 진행중 경매 + 상세/상태 | daily + 3h 폴링 |
| 번개장터 | `run.py bunjang` | 비공식 API | 국내 중고 호가 + 등록일/지역 | daily |
| 아미아미 | `run.py amiami` | Playwright(CF우회) | **일본 정가 + 발매일 + JAN바코드** | weekly |
| 야후옥션JP | `run.py yahoo` | __NEXT_DATA__ JSON | **일본 중고 낙찰가=실거래** | daily |
| HLJ | `run.py hlj` | search HTML + livePrice JSON | **해외 새제품 정가**(JPY)+발매일 | weekly |
| BBTS | `run.py bbts` | Playwright(CF) + DOM 파싱 | **미국 새제품 정가**(USD) | weekly |
| 스루가야 | `run.py suruga` | FlareSolverr(CF) + GTM JS | **일본 중고 정찰가**(JPY) | weekly(FlareSolverr 필요) |
| 다나와 | `run.py danawa` | dsearch HTML | **국내 가격비교 최저가**(KRW) 602행 | daily |
| Hobby Search | `run.py hobbysearch` | FlareSolverr(CF) + c-card | **일본 새제품 정가**(JPY) 263행 | weekly(FlareSolverr) |
| Entertainment Earth | `run.py entearth` | FlareSolverr(CF) + data-* | **미국 새제품 정가**(USD) 301행 | weekly(FlareSolverr) |
| 라쿠텐 | `run.py rakuten` | 공식 Ichiba API | **일본 신품/중고 호가**(JPY) | ⏸ **보류**(일본폰 인증 필요) |
| eBay | `run.py ebay` | 공식 API | 해외 호가 | ⏸ **키 발급 대기중** |

**자동화 (Windows 작업 스케줄러)**:
- `FiguresAnalysisDaily` 09:00 + `FiguresAnalysis_Daily` 20:00 — `run.py daily`(호가/실거래: naver+wyyyes+bunjang+yahoo→리포트→HTML)
- `FiguresWeekly` — 일요일 10:00, `run.py weekly`(정가+중고: amiami+hlj+bbts+**suruga**→group→premium/pricing→HTML). ⚠️ suruga는 FlareSolverr 도커 필요(없으면 skip).
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

### 보류 (인프라 필요) — 2026-06-24#4 재정찰 결과 추가
- ✅ **스루가야 — 해결(FlareSolverr 도입)**. 위 #4b 참조. 더이상 보류 아님.
- **만다라케 — 미해결(게이트)**: `order.mandarake.co.jp/order/listPage/list?keyword=`·`order/?lang=en` 모두 **splash(title=MANDARAKE, ~9551byte 고정)**만 반환. **FlareSolverr(실브라우저 JS실행)로도 splash 그대로** → CF/JS리다이렉트 아님. lang=ja·dispCount·categoryCode·쿠키(language/over18) 변형 전부 splash. 게이트가 **지역/IP 또는 깊은 세션플로 기반** 추정(한국IP 차단 가능성). 리버싱 or 일본 프록시 필요. **단 스루가야가 일본중고 카테고리 이미 커버 → 만다라케 마진가치 낮음, 후순위.**
- **Nin-Nin-Game**: PrestaShop(`/en/search?s=`)인데 검색결과 **JS렌더(XHR도 안잡힘)** + 빠른요청에 **403(WAF, administrative rules)**. 일본정가는 amiami/HLJ로 이미 커버 → **저가치라 보류 권장**.
- **메루카리 JP**: DPoP 토큰. mercapi 라이브러리 or 유료 Apify.
- **국내 옥션/G마켓**: 403. **당근/중고나라**: 봇차단·인증. 전용 인프라.
- 📌 결론: 코드만으로 가능한 신규소스는 이번에 **HLJ·BBTS 추가로 소진**. 남은 건 전부 ① 사용자작업(eBay 키) or ② stealth/프록시 인프라. **다음 사이트 확장 전 인프라(예: FlareSolverr 도커 1개) 도입 결정 필요**.

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
