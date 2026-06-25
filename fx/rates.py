"""환율 수집 (무료, 키 불필요): open.er-api.com.

USD->KRW, JPY->KRW 저장. 네이버 가격은 이미 KRW라 Phase1에선 보조용,
Phase2 eBay(USD)/야후(JPY) 보정에 사용.
"""
import datetime
import requests

from storage.db import get_conn

ENDPOINT = "https://open.er-api.com/v6/latest/{base}"


def fetch_rate(base: str) -> float:
    """1 base = ? KRW"""
    r = requests.get(ENDPOINT.format(base=base), timeout=20)
    r.raise_for_status()
    data = r.json()
    return float(data["rates"]["KRW"])


def update_fx(today: str | None = None):
    if today is None:
        today = datetime.date.today().isoformat()
    conn = get_conn()
    for base in ("USD", "JPY", "PHP"):
        rate = fetch_rate(base)
        conn.execute(
            "INSERT OR REPLACE INTO fx_rate(date, base, quote, rate) VALUES (?,?,?,?)",
            (today, base, "KRW", rate),
        )
        print(f"[fx] {today} 1 {base} = {rate:.4f} KRW")
    conn.commit()
    conn.close()


if __name__ == "__main__":
    update_fx()
