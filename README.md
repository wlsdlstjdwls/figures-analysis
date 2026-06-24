# figures-analysis

피규어 시장 가격·인기 분석 시스템. 상세 설계는 [PLAN.md](PLAN.md).

## 현재 소스
- **네이버 쇼핑** API — 국내 새제품 호가
- **와이스(WYYYES)** 비공식 API — 국내 **낙찰가(실거래)** + 진행중 경매. 컬렉터 거래 앱.
- **eBay** Browse API — 해외 호가 (키 발급 후)
- 저장: SQLite (`data/figures.db`) · 분석: 장르/제조사/캐릭터별 가격분포 + 인기 랭킹 + 실거래/호가 구분

## 설치
```
pip install -r requirements.txt
cp .env.example .env   # 네이버 Client ID/Secret 입력
```

## 실행
```
python run.py all        # 환율 -> 수집 -> 분석 (콘솔 출력)
python run.py daily      # 환율 -> 수집 -> 리포트 + HTML (자동화용)
python run.py collect    # 네이버 수집만
python run.py ebay       # eBay Browse 수집 (해외 호가, EBAY_APP_ID/CERT 필요)
python run.py wyyyes     # WYYYES(와이스) 수집 (국내 낙찰가=실거래 + 진행중 경매)
python run.py analyze    # 분석 콘솔 출력
python run.py report     # reports/report_<날짜>.md 생성
python run.py html       # reports/dashboard.html 생성 (브라우저 대시보드)
python run.py timeseries # 시계열 추이 (여러 날 누적 필요)
```
Windows 콘솔 한글 깨지면: `$env:PYTHONIOENCODING="utf-8"` 먼저 실행.

## 화면에서 보기
- **대시보드**: `python run.py html` 후 `reports/dashboard.html` 더블클릭(브라우저). 차트 + 정렬 가능한 표.
- **마크다운 리포트**: `reports/report_<날짜>.md` (VS Code 미리보기 `Ctrl+Shift+V` 또는 GitHub).
- **콘솔**: `python run.py analyze`.

## 자동화 (시계열 누적)
Windows 작업 스케줄러에 `FiguresAnalysisDaily` 등록됨 — 매일 09:00 `run_daily.bat`(=`run.py daily`) 실행.
스냅샷이 쌓이면 `timeseries` 가 가격 추이/급변을 잡는다.
(분석/리포트는 상품별 **최신 스냅샷 1건**만 집계 → 중복 스냅샷 카운트 안 됨.)

## 구조
```
collectors/api/naver.py   네이버 수집기
normalize/extract.py      상품명 -> 구조화 (룰 기반, Phase2 LLM 보강)
fx/rates.py               환율 (USD/JPY -> KRW)
storage/                  스키마 + DB
analysis/price.py         가격분포·랭킹
run.py                    진입점
```

## 다음 (Phase2)
야후옥션(실거래가) · Surugaya · eBay Browse 추가, LLM 상품명 정규화, 시계열 누적.
