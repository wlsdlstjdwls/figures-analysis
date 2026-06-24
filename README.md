# figures-analysis

피규어 시장 가격·인기 분석 시스템. 상세 설계는 [PLAN.md](PLAN.md).

## Phase1 MVP (현재)
- 소스: 네이버 쇼핑 검색 API (국내 새제품 호가)
- 저장: SQLite (`data/figures.db`)
- 분석: 제조사/라인/캐릭터별 가격분포 + 인기 랭킹

## 설치
```
pip install -r requirements.txt
cp .env.example .env   # 네이버 Client ID/Secret 입력
```

## 실행
```
python run.py all        # 환율 -> 수집 -> 분석 (콘솔 출력)
python run.py daily      # 환율 -> 수집 -> 리포트 파일 (자동화용)
python run.py collect    # 수집만
python run.py analyze    # 분석 출력
python run.py report     # reports/report_<날짜>.md 생성
python run.py timeseries # 시계열 추이 (여러 날 누적 필요)
```
Windows 콘솔 한글 깨지면: `$env:PYTHONIOENCODING="utf-8"` 먼저 실행.

## 자동화 (시계열 누적)
매일 1회 `python run.py daily` 를 Windows 작업 스케줄러 또는 `/schedule` 루틴으로 등록.
스냅샷이 쌓이면 `timeseries` 가 가격 추이/급변을 잡는다.

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
