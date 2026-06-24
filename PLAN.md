# 피규어 시장 데이터 수집·분석 시스템 기획서

> 작성일: 2026-06-24 (rev.2)
> 범위: 해외(eBay) · 일본(駿河屋/AmiAmi/Yahoo) · 한국 새제품(네이버쇼핑) · 한국 중고(번개장터/당근)
> 목표: 가격형성·시세, 인기 랭킹, 시계열 추세, 자동 리포트
> **카테고리 집중: 소프비(soft vinyl) — 괴수/공룡/특촬 중점 + 기타 전 분야.** 고질라·울트라맨·가메라·가면라이더 등.

> **rev.2 변경점**: eBay 실거래가(sold)는 Marketplace Insights = 비즈니스 승인 제한 API라 개인용 확보 불가 가능성 큼. → **실거래 앵커를 야후옥션 낙찰가로 재정렬**. API 발급 절차·비용/한도 섹션(§10, §11) 추가.

---

## 1. 목적 / 핵심 질문

이 시스템이 답해야 하는 질문:

1. **가격형성** — 같은 피규어가 시장·국가별로 얼마에 거래되나? 한일 가격차, 환율 보정 후 실질가, 호가 대비 실거래가 괴리.
2. **인기 랭킹** — 어떤 캐릭터/제조사/라인이 잘 팔리나? (검색량·거래량·품절률·프리미엄율 기준)
3. **시계열 추세** — 시간에 따른 가격·인기 변동. 발매 후 프리미엄 붙는 제품 식별.
4. **자동 리포트** — 주간 자동 수집 → 분석 → 리포트 발행.

핵심 원칙: **호가(asking price)와 실거래가(sold price)를 반드시 구분**한다. 호가만 모으면 시세가 왜곡된다.

**실거래 앵커 (rev.2 재정렬)**:
1순위 = **야후옥션 JP 낙찰가** — 접근 가능한 가장 신뢰할 실거래 소스.
2순위 = **駿河屋(Surugaya) 실판매 시세** — 정가+중고 매입/판매가 표기.
참고 = eBay Browse(활성 호가만). eBay sold는 Marketplace Insights 제한 API라 개인 확보 어려움(§10 참고).

---

## 2. 데이터 모델

### 2.1 정규화 스키마 (product_listing)

| 필드 | 타입 | 설명 |
|------|------|------|
| `id` | PK | 내부 ID |
| `source` | enum | ebay / surugaya / amiami / yahoo_auction / naver / bunjang / danggn |
| `source_item_id` | str | 원본 사이트 상품 ID |
| `title_raw` | str | 원본 상품명 |
| `character` | str | 정규화된 캐릭터/IP (예: 原神-라이덴) |
| `maker` | str | 제조사 (Good Smile / Kotobukiya / Banpresto / MegaHouse …) |
| `line` | str | 라인 (Nendoroid / figma / 1-7scale / prize / pop-up-parade) |
| `scale` | str | 1/7, 1/4, non-scale |
| `condition` | enum | new / used_sealed / used_open / prize |
| `price` | decimal | 원본 통화 가격 |
| `currency` | enum | USD / JPY / KRW |
| `price_krw` | decimal | 수집 시점 환율 보정 가격 (분석 통일 기준) |
| `is_sold` | bool | 실거래 여부 (false=호가) |
| `listed_at` / `sold_at` | datetime | |
| `collected_at` | datetime | 수집 시각 |
| `url` | str | |

### 2.2 마스터 테이블

- `product_master` — 동일 제품을 사이트 간 매칭 (캐릭터+제조사+라인+스케일 키 또는 JAN/바코드).
- `fx_rate` — 일자별 환율 (USD/JPY → KRW). 환율 보정 재현성 위해 시점 고정 저장.

### 2.3 제품 매칭 (핵심 난제)

사이트마다 상품명 표기 제각각 → 같은 제품 묶기 어려움.
- 1차: JAN/바코드(아미아미·스루가야 제공) 매칭.
- 2차: 제조사+라인+캐릭터 정규화 후 퍼지 매칭.
- 3차: LLM(Claude)로 상품명 → 구조화 필드 추출. **이 단계가 Claude Code의 핵심 가치.**

---

## 3. 소스별 수집 전략

| 시장 | 사이트 | 방식 | 데이터 품질 | 난이도 | 비고 |
|------|--------|------|-------------|--------|------|
| 일본 | **Yahoo Auction JP** | 공식 API(일부)/스크랩 | ★★★ **낙찰가=실거래** | 중 | **실거래 앵커 1순위** |
| 일본 | 駿河屋 Surugaya | 스크랩 | ★★★ 정가+중고 시세 | 중 | 바코드 보유, 매칭 유리. 실거래 2순위 |
| 해외 | eBay (Browse) | 공식 API | ★★ 활성 호가만 | 낮음 | sold는 제한 API(§10). 호가·해외수요 참고용 |
| 일본 | AmiAmi | 스크랩 | ★★ 새제품/예약 | 중 | 정가·할인율 기준 |
| 한국 | 네이버쇼핑 | 검색 API (공식) | ★★ 새제품 호가 | 낮음 | 안정적, 국내 시세 |
| 한국 | 번개장터 | 비공식 API / 스크랩 | ★★ 중고 호가 | 높음 | 봇차단, IP밴 위험 |
| 한국 | 당근마켓 | 스크랩 | ★ 지역 호가 | 높음 | 적대적, 신중 |

### 3.1 합법성 / 운영 원칙
- robots.txt + ToS 준수. 정식 API 최우선 (eBay, 네이버, 야후재팬).
- rate limit 보수적 설정 (사이트당 동시 1, 요청 간 지연).
- User-Agent 명시, 캐싱으로 중복요청 제거.
- 봇차단 강한 한국 중고(번개·당근)는 **저빈도·소량 수집**으로 리스크 관리. 차단 시 자동 백오프.

---

## 4. 시스템 아키텍처

```
[수집 레이어]  소스별 Collector (Python)
   - api_collectors/   eBay, 네이버, 야후
   - scrapers/         Surugaya, AmiAmi, 번개, 당근 (Playwright)
        │  raw JSON 저장 (재처리 대비)
        ▼
[정규화 레이어]  Normalizer
   - 상품명 → 구조화 필드 (룰 + Claude LLM 추출)
   - 환율 보정 (fx_rate 조인)
   - product_master 매칭
        ▼
[저장소]  SQLite(MVP) → Postgres(확장)
        ▼
[분석 레이어]  pandas / 분석 모듈
   - 가격형성 / 인기랭킹 / 시계열
        ▼
[리포트 레이어]  주간 마크다운/HTML 리포트 + 이상탐지 알림
```

### 4.1 디렉토리 구조 (예정)
```
figures-analysis/
├── PLAN.md                  ← 본 문서
├── collectors/
│   ├── api/ ebay.py naver.py yahoo.py
│   └── scrape/ surugaya.py amiami.py bunjang.py danggn.py
├── normalize/
│   ├── extract.py           룰 기반 파싱
│   ├── llm_extract.py       Claude 상품명 구조화
│   └── match.py             product_master 매칭
├── storage/ schema.sql  db.py
├── analysis/
│   ├── price.py  ranking.py  timeseries.py
├── report/ weekly.py  templates/
├── fx/ rates.py
└── config.yaml
```

---

## 5. 분석 설계

### 5.1 가격형성 / 시세
- 제품별 가격분포: median / p25 / p75 / 이상치 제거(IQR).
- **한일 가격차**: 동일 제품 price_krw 비교 → 직구 차익 지표.
- **호가 vs 실거래 괴리율**: (median 호가 − median 실거래) / 실거래.
- **프리미엄율**: 현재 중고 시세 / 발매 정가. >1 이면 프리미엄.

### 5.2 인기 랭킹
- 점수 = 가중합(거래량, 검색노출, 품절률, 프리미엄율).
- 차원별 랭킹: 캐릭터 / 제조사 / 라인 / IP.
- 신규 급상승(시계열 기울기) 별도 표기.

### 5.3 시계열 추세
- 제품별 주간 시세 곡선. 발매 후 N주 프리미엄 곡선 패턴화.
- 이벤트(애니 방영·재판) 전후 가격 변동 탐지.

### 5.4 자동 리포트 (주간)
- 이번 주 인기 TOP N, 시세 급변 제품, 한일 차익 TOP, 신규 프리미엄 제품.
- 마크다운 + 차트. 이상탐지 시 알림.

---

## 6. 자동화 / 원격 Claude Code 루틴

| 작업 | 적합 위치 | 이유 |
|------|-----------|------|
| API 수집 (eBay/네이버/야후) | 원격 루틴 OK | 가볍고 안정적 |
| 브라우저 스크랩 (Surugaya/번개/당근) | **전용 서버 권장** | 원격 환경 브라우저/IP차단/캡차 약함 |
| 정규화 LLM 추출 | Claude Code 핵심 | 상품명 구조화 = LLM 강점 |
| 분석 + 리포트 | 원격 루틴 OK | 데이터만 있으면 가벼움 |
| 이상탐지·요약 | Claude Code 핵심 | 자연어 인사이트 |

권장 분담: **수집(특히 스크랩)은 별도 스케줄러/서버, Claude Code는 정규화·분석·리포트·이상탐지 오케스트레이션** 담당. `/schedule` 크론으로 주간 분석 루틴 등록 가능.

---

## 7. 단계별 로드맵

**Phase 0 — 기획 (현재)**: 본 문서.

**Phase 1 — MVP**:
- **네이버쇼핑 API**(국내 새것 호가) + **eBay Browse API**(해외 호가/수요) 2개 소스.
- 인기 라인 1개 고정(예: 넨도로이드) 수집.
- SQLite 저장 + 환율 보정.
- 가격분포·한일차·간이 랭킹 분석.
- ※ 실거래가는 Phase 2 야후옥션부터. MVP는 호가 기반 + 구조 검증 목적.

**Phase 2 — 확장**:
- Surugaya/AmiAmi/야후 추가. 제품 매칭(바코드).
- LLM 상품명 정규화 본격화.
- 시계열 누적 시작.

**Phase 3 — 자동화**:
- 한국 중고(번개/당근) 저빈도 수집.
- 주간 자동 리포트 + `/schedule` 루틴.
- 이상탐지 알림.

---

## 8. 리스크 / 미해결 이슈

- **스크랩 차단**: 번개·당근 적대적. 차단 시 데이터 공백 → 한국 중고 시세 신뢰도 저하 가능.
- **제품 매칭 정확도**: 사이트 간 동일 제품 묶기. 바코드 없는 중고는 LLM 매칭 의존 → 오매칭 검증 필요.
- **환율 시점**: 보정 기준 일자 고정 정책 확정 필요.
- **실거래 데이터 부족 (rev.2 격상)**: eBay sold = Marketplace Insights 제한 API, 개인 확보 어려움. 실거래 앵커를 야후옥션 낙찰가에 의존 → 야후 접근 차단 시 전체 실거래 신뢰도 타격. Surugaya 시세를 백업 앵커로 병행.
- **법적**: 각 사이트 ToS 재확인. 정식 API 가능한 곳은 무조건 API.
- **[실측 2026-06-24] Surugaya 스크랩 403 Forbidden** — 단순 requests+UA로 차단됨. 브라우저(Playwright)·쿠키·프록시 또는 전용 인프라 필요 확인. 원격 루틴 부적합 재확인 → 일본 실거래는 야후옥션 정식 API 우선 추진.

---

## 9. 다음 결정 필요

1. ~~eBay/네이버 API 키 발급 주체~~ → 발급 절차 §10 확정. **사용자 계정으로 키 발급 진행 필요.**
2. 고정 수집 대상 라인/IP 선정 (MVP 범위 좁히기).
3. 수집 인프라 — 로컬 PC 상시구동 vs 클라우드 서버 vs 원격 루틴.
4. 환율 소스 (한국은행 API / 무료 FX API).
5. eBay Marketplace Insights(sold) 비즈니스 승인 시도 여부 — 안 되면 야후옥션 의존 확정.

---

## 10. API 발급 절차 (실무)

### 10.1 네이버 검색 API (난이도 낮음, 즉시 발급)
1. https://developers.naver.com 로그인.
2. Application → **애플리케이션 등록**.
3. **사용 API = "검색"** 선택 (필수).
4. 비로그인 오픈API → **WEB 설정** + 서비스 URL 입력 → 등록.
5. **Client ID / Client Secret** 발급.
6. 권한관리 탭에서 "검색" 체크 확인 (미체크 시 **403**).
7. 호출: `GET openapi.naver.com/v1/search/shop.json` + 헤더 `X-Naver-Client-Id`, `X-Naver-Client-Secret`.
- 한도: **일 25,000회 무료**. 응답에 가격(최저가) / 쇼핑몰 / 카테고리.

### 10.2 eBay API (난이도 중, sold는 별도 승인)
1. https://developer.ebay.com 가입 (Developers Program).
2. Application Keys → **Production** keyset 생성 → **App ID(Client ID) + Cert ID(Client Secret)**.
3. **Production 활성화 조건**: marketplace account deletion 알림 구독/옵트아웃 필수.
4. OAuth **Client Credentials** grant → application access token.
5. **Browse API** 호출(`/buy/browse/v1/item_summary/search`) → 활성 매물(호가).
6. ⚠️ **Sold price = Marketplace Insights API** → *Limited Release*. Application Growth Check 비즈니스 모델 심사 필요, 개인·비상업 거절 가능성 높음.
- 한도: Browse API 무료 티어 약 5,000 call/day 수준(앱별 상이, 콘솔 확인).

### 10.3 야후옥션 JP (Phase 2, 실거래 앵커)
- Yahoo! Developer Network 앱 등록 → Auction API. 단 일부 옥션 API 신규발급 제한 이력 → 발급 가능 여부 선확인. 불가 시 스크랩 백업.

---

## 11. 비용 / 한도 / 인프라 요약

| 항목 | 비용 | 한도 | 비고 |
|------|------|------|------|
| 네이버 검색 API | 무료 | 25,000/일 | 충분 |
| eBay Browse API | 무료 | ~5,000/일 | 앱별 확인 |
| eBay Marketplace Insights | 무료(승인 시) | 승인 게이트 | 개인 어려움 |
| 야후옥션 API | 무료 | 앱별 | 발급 가능여부 확인 |
| 스크랩(Surugaya 등) | 인프라비만 | self rate-limit | Playwright |
| 환율 API | 무료 | — | 한국은행/exchangerate-api |
| Claude(정규화/리포트) | 토큰 종량 | — | LLM 추출·분석 |
| 저장소 | SQLite 무료→Postgres | — | 확장 시 클라우드 |

인프라 선택지: ① 로컬 상시구동(무료, PC 켜둬야 함) ② VPS 소형(월 5~10달러, 스크랩 안정) ③ 원격 루틴(API수집·분석만, 스크랩 약함). **권장: API수집+분석=원격루틴/VPS, 무거운 스크랩=VPS.**
