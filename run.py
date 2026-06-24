"""Phase1 MVP 실행 진입점.

  python run.py init      # DB 초기화
  python run.py fx        # 환율 갱신
  python run.py collect   # 네이버 수집
  python run.py ebay      # eBay Browse 수집 (해외 호가, 키 필요 §10.2)
  python run.py wyyyes    # WYYYES 수집 (국내 낙찰가=실거래 + 진행중 경매)
  python run.py bunjang   # 번개장터 수집 (국내 중고 호가)
  python run.py amiami    # 아미아미 수집 (일본 정가+발매일+바코드, Playwright)
  python run.py analyze   # 분석 출력
  python run.py timeseries# 시계열 추이 (누적 데이터 필요)
  python run.py report    # 주간 마크다운 리포트 생성
  python run.py html      # HTML 대시보드 생성 (reports/dashboard.html)
  python run.py all       # fx -> collect -> analyze
  python run.py daily     # fx -> collect -> report + html  (자동화용)
"""
import sys


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"

    if cmd == "init":
        from storage.db import init_db
        init_db()
    elif cmd == "fx":
        from fx.rates import update_fx
        update_fx()
    elif cmd == "collect":
        from collectors.api.naver import collect
        collect()
    elif cmd == "ebay":
        from collectors.api.ebay import collect
        collect()
    elif cmd == "wyyyes":
        from collectors.api.wyyyes import collect
        collect()
    elif cmd == "bunjang":
        from collectors.api.bunjang import collect
        collect()
    elif cmd == "amiami":
        from collectors.scrape.amiami import collect
        collect()
    elif cmd == "analyze":
        from analysis.price import run
        run()
    elif cmd == "timeseries":
        from analysis.timeseries import run
        run()
    elif cmd == "report":
        from report.weekly import build
        build()
    elif cmd == "html":
        from report.html_report import build
        build()
    elif cmd == "daily":
        from storage.db import init_db
        from fx.rates import update_fx
        from collectors.api.naver import collect
        from collectors.api.wyyyes import collect as collect_wyyyes
        from collectors.api.bunjang import collect as collect_bunjang
        from report.weekly import build
        from report.html_report import build as build_html
        init_db()
        try:
            update_fx()
        except Exception as e:
            print(f"[fx] skip ({e})")
        collect()
        try:
            collect_wyyyes()
        except Exception as e:
            print(f"[wyyyes] skip ({e})")
        try:
            collect_bunjang()
        except Exception as e:
            print(f"[bunjang] skip ({e})")
        build()
        build_html()
    elif cmd == "all":
        from storage.db import init_db
        from fx.rates import update_fx
        from collectors.api.naver import collect
        from analysis.price import run
        init_db()
        try:
            update_fx()
        except Exception as e:
            print(f"[fx] skip ({e})")
        collect()
        run()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
