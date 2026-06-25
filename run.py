"""Phase1 MVP 실행 진입점.

  python run.py init      # DB 초기화
  python run.py fx        # 환율 갱신
  python run.py collect   # 네이버 수집
  python run.py ebay      # eBay Browse 수집 (해외 호가, 키 필요 §10.2)
  python run.py wyyyes    # WYYYES 수집 (국내 낙찰가=실거래 + 진행중 경매)
  python run.py bunjang   # 번개장터 수집 (국내 중고 호가)
  python run.py amiami    # 아미아미 수집 (일본 정가+발매일+바코드, Playwright)
  python run.py yahoo     # 야후옥션 재팬 (일본 중고 낙찰가=실거래 + 호가)
  python run.py hlj       # HLJ(HobbyLink Japan) 수집 (해외 새제품 정가, requests)
  python run.py bbts      # BBTS(BigBadToyStore) 수집 (미국 새제품 정가, Playwright)
  python run.py suruga    # 스루가야 수집 (일본 중고 정찰가, FlareSolverr 경유)
  python run.py rakuten   # 라쿠텐 이치바 수집 (일본 신품/중고 호가, 무료 API키 필요)
  python run.py danawa    # 다나와 수집 (국내 가격비교 최저가 호가, requests)
  python run.py hobbysearch # Hobby Search(1999.co.jp) 수집 (일본 새제품 정가, FlareSolverr)
  python run.py entearth  # Entertainment Earth 수집 (미국 새제품 정가, FlareSolverr)
  python run.py solaris   # Solaris Japan 수집 (일본 피규어 새제품 정가+중고 호가 USD, requests)
  python run.py toynk     # Toynk 수집 (미국 새제품 정가 USD, requests)
  python run.py cmdstore  # CMD Store 수집 (미국 새제품 정가 USD, requests)
  python run.py ninoma    # Ninoma 수집 (필리핀 새제품 호가 PHP, requests)
  python run.py galactictoys # Galactic Toys 수집 (미국 새제품 정가 USD, requests, ⭐괴수풍부)
  python run.py toyshnip  # Toyshnip 수집 (미국 일본직수입 새제품 정가 USD, requests)
  python run.py analyze   # 분석 출력
  python run.py match     # 교차언어 상품 매칭 후보 덤프 (판정은 Claude Code가 대화로)
  python run.py group     # 상품그룹 매칭 (이관+자동블로킹+검수덤프+product_match 역생성)
  python run.py premium   # 프리미엄율 (매칭 있으면 상품단위, 없으면 세그먼트 근사)
  python run.py pricing   # 판매가 추천 (매칭 상품별 시세→권장가, 실거래 우선)
  python run.py timeseries# 시계열 추이 (누적 데이터 필요)
  python run.py report    # 주간 마크다운 리포트 생성
  python run.py html      # HTML 대시보드 생성 (reports/dashboard.html)
  python run.py all       # fx -> collect -> analyze
  python run.py daily     # fx -> 호가/실거래(naver/wyyyes/bunjang/yahoo) -> report + html (매일 자동)
  python run.py weekly    # fx -> 정가+스루가야(amiami/hlj/bbts/suruga) -> group -> premium/pricing -> html (주1회 자동, suruga는 FlareSolverr 필요)
"""
import sys


def main():
    # Windows 콘솔(cp949)에서 한글/nbsp 등 출력 시 UnicodeEncodeError 방지
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

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
    elif cmd == "yahoo":
        from collectors.scrape.yahoo_jp import collect
        collect()
    elif cmd == "hlj":
        from collectors.scrape.hlj import collect
        collect()
    elif cmd == "bbts":
        from collectors.scrape.bbts import collect
        collect()
    elif cmd == "suruga":
        from collectors.scrape.suruga import collect
        collect()
    elif cmd == "rakuten":
        from collectors.api.rakuten import collect
        collect()
    elif cmd == "danawa":
        from collectors.scrape.danawa import collect
        collect()
    elif cmd == "hobbysearch":
        from collectors.scrape.hobbysearch import collect
        collect()
    elif cmd == "entearth":
        from collectors.scrape.entearth import collect
        collect()
    elif cmd == "solaris":
        from collectors.scrape.solaris import collect
        collect()
    elif cmd == "toynk":
        from collectors.scrape.toynk import collect
        collect()
    elif cmd == "cmdstore":
        from collectors.scrape.cmdstore import collect
        collect()
    elif cmd == "ninoma":
        from collectors.scrape.ninoma import collect
        collect()
    elif cmd == "galactictoys":
        from collectors.scrape.galactictoys import collect
        collect()
    elif cmd == "toyshnip":
        from collectors.scrape.toyshnip import collect
        collect()
    elif cmd == "analyze":
        from analysis.price import run
        run()
    elif cmd == "match":
        from normalize.llm_match import run
        run()
    elif cmd == "group":
        from normalize.grouping import run
        run()
    elif cmd == "renormalize":
        from normalize.extract import renormalize
        renormalize()
    elif cmd == "premium":
        from analysis.premium import run
        run()
    elif cmd == "pricing":
        from analysis.pricing import run
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
        # 매일 변동(호가/실거래)만 — 가볍게. 정가(Playwright/CF)는 weekly로 분리.
        from storage.db import init_db
        from fx.rates import update_fx
        from collectors.api.naver import collect
        from collectors.api.wyyyes import collect as collect_wyyyes
        from collectors.api.bunjang import collect as collect_bunjang
        from collectors.scrape.yahoo_jp import collect as collect_yahoo
        from collectors.scrape.danawa import collect as collect_danawa
        from report.weekly import build
        from report.html_report import build as build_html
        init_db()
        try:
            update_fx()
        except Exception as e:
            print(f"[fx] skip ({e})")
        collect()
        for name, fn in (("wyyyes", collect_wyyyes), ("bunjang", collect_bunjang),
                         ("yahoo", collect_yahoo), ("danawa", collect_danawa)):
            try:
                fn()
            except Exception as e:
                print(f"[{name}] skip ({e})")
        build()
        build_html()
    elif cmd == "weekly":
        # 주1회 정가 소스(Playwright/CF 무거움) + 재그룹 + 분석 + HTML 재생성.
        from storage.db import init_db
        from fx.rates import update_fx
        from collectors.scrape.amiami import collect as collect_amiami
        from collectors.scrape.hlj import collect as collect_hlj
        from collectors.scrape.bbts import collect as collect_bbts
        from collectors.scrape.suruga import collect as collect_suruga
        from collectors.scrape.hobbysearch import collect as collect_hs
        from collectors.scrape.entearth import collect as collect_ee
        from collectors.scrape.solaris import collect as collect_solaris
        from collectors.scrape.toynk import collect as collect_toynk
        from collectors.scrape.cmdstore import collect as collect_cmd
        from collectors.scrape.ninoma import collect as collect_ninoma
        from collectors.scrape.galactictoys import collect as collect_galactic
        from collectors.scrape.toyshnip import collect as collect_toyshnip
        from collectors.api.rakuten import collect as collect_rakuten
        from report.html_report import build as build_html
        init_db()
        try:
            update_fx()
        except Exception as e:
            print(f"[fx] skip ({e})")
        for name, fn in (("amiami", collect_amiami), ("hlj", collect_hlj),
                         ("bbts", collect_bbts), ("suruga", collect_suruga),
                         ("hobbysearch", collect_hs), ("entearth", collect_ee),
                         ("solaris", collect_solaris), ("toynk", collect_toynk),
                         ("cmdstore", collect_cmd), ("ninoma", collect_ninoma),
                         ("galactictoys", collect_galactic), ("toyshnip", collect_toyshnip),
                         ("rakuten", collect_rakuten)):
            try:
                fn()
            except Exception as e:
                print(f"[{name}] skip ({e})")
        try:
            from normalize.grouping import run as run_group
            run_group()
        except Exception as e:
            print(f"[group] skip ({e})")
        for name, mod in (("premium", "analysis.premium"), ("pricing", "analysis.pricing")):
            try:
                __import__(mod, fromlist=["run"]).run()
            except Exception as e:
                print(f"[{name}] skip ({e})")
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
