# 다음 작업 / 세션 인계 문서

> 최종 업데이트: 2026-06-24 · 수집 검색어 한일 정렬로 겹침↑ → 상품매칭 6건. (교차언어 매칭=Claude Code 직접, 유료 API 미사용)
> 새 세션에서 이 파일부터 읽으면 이어서 작업 가능. 전체 설계는 [PLAN.md](PLAN.md).

## 현재 상태 (한눈에)

**데이터**: SQLite `data/figures.db` (gitignore 제외, 로컬 전용). 약 1.4만행.
- 소스별: 네이버 3,360 · 번개장터 881 · 아미아미 433 · 와이스 39 (상품별 최신 기준 ~4,700건)
- 모든 행 한 테이블 `product_listing`. `collected_at`로 스냅샷 누적 → 시계열 가능. 분석은 상품별 최신 1건.

**연동 완료 소스 (5)**:
| 소스 | 명령 | 방식 | 데이터 | 자동수집 |
|------|------|------|--------|----------|
| 네이버쇼핑 | `run.py collect` | 공식 API | 국내 새제품 호가 | daily |
| 와이스 | `run.py wyyyes` | 비공식 JSON API | **국내 낙찰가=실거래** + 진행중 경매 + 상세/상태 | daily + 3h 폴링 |
| 번개장터 | `run.py bunjang` | 비공식 API | 국내 중고 호가 + 등록일/지역 | daily |
| 아미아미 | `run.py amiami` | Playwright(CF우회) | **일본 정가 + 발매일 + JAN바코드** | 수동(주1회 권장) |
| eBay | `run.py ebay` | 공식 API | 해외 호가 | ⏸ **키 발급 대기중** |

**자동화 (Windows 작업 스케줄러)**:
- `FiguresAnalysisDaily` — 매일 09:00, 전체 수집→리포트→HTML
- `FiguresWyyyesPoll` — 3시간마다, 와이스 낙찰가 누적
- ⚠️ PC 켜져 있어야 실행. 24시간 원하면 VPS.

**화면**: `reports/dashboard.html` (상품 카드 그리드). 검색·출처/구분/장르 필터·정렬(가격/날짜 최신·오래된순)·보기모드(갤러리/그리드/리스트)·모바일 반응형. 카드: **출처 색상뱃지**·이미지·가격·실거래/호가·상태·연식·**📅 날짜(발매/등록/거래, 라벨화)**·🏬매장·설명. 상단 **💹 프리미엄 섹션**(접이식). ⚠️ naver는 source_date 없음 → 날짜정렬 시 뒤로.

---

## 다음 할일 (우선순위)

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
python run.py daily      # 전체 수집 + 리포트 + HTML
python run.py amiami     # 아미아미만 (Playwright)
start reports/dashboard.html
```
