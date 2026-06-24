# 다음 작업 / 세션 인계 문서

> 최종 업데이트: 2026-06-24 · 최신 커밋 `d82c654`
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

**화면**: `reports/dashboard.html` (상품 카드 그리드). 검색·출처/구분/장르 필터·가격정렬·보기모드(갤러리/그리드/리스트)·모바일 반응형. 카드: 이미지·가격·실거래/호가·상태·연식·발매일·매장·설명.

---

## 다음 할일 (우선순위)

### 1순위 ⭐ 프리미엄율 분석 화면 (지금 데이터로 바로 가능)
- 목적: "정가 대비 중고가 몇 % 프리미엄?" = 핵심 인사이트 (PLAN §5.1).
- 재료 다 있음: 아미아미 **정가+JAN바코드** ↔ 와이스/번개 **중고 실거래/호가**.
- 작업:
  1. 바코드(`barcode`) 우선 매칭 → 없으면 캐릭터+제조사+제목 퍼지 매칭 (PLAN §2.3).
  2. 제품별 `중고 중앙가 / 정가` = 프리미엄율 계산.
  3. 대시보드에 "프리미엄 TOP" 섹션 or 별도 뷰 + 정가↔중고 비교.
- 주의: 현재 바코드는 아미아미만 보유. 국내 중고(와이스/번개)엔 바코드 없음 → 퍼지매칭 정확도가 관건. LLM(Claude) 매칭 도입 검토(PLAN §2.3 3차).

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
