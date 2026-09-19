# -*- coding: utf-8 -*-
"""WTI / Brent 价格快照，多级免 key 兜底。

顺序：CNBC 实时期货报价 -> FRED 现货日线 CSV -> Stooq 期货日线 CSV。
任一来源成功即返回，并记录实际使用的来源；全部失败时记录 error，不阻断报告生成。
"""
import csv
import io
from datetime import datetime
from typing import Dict, Optional

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (oilwatch)"}
TIMEOUT = 15

# 各品种在三个源下的代码
CNBC_SYMBOLS = {"WTI": "@CL.1", "Brent": "@LCO.1"}
FRED_SERIES = {"WTI": "DCOILWTICO", "Brent": "DCOILBRENTEU"}
STOOQ_SYMBOLS = {"WTI": "cl.f", "Brent": "cb.f"}


def _empty(error: Optional[str] = None) -> Dict[str, Optional[float]]:
    return {"date": None, "close": None, "prev_close": None,
            "change": None, "pct_change": None, "source": None, "error": error}


def _from_cnbc(name: str) -> Dict[str, Optional[float]]:
    sym = CNBC_SYMBOLS[name]
    url = ("https://quote.cnbc.com/quote-html-webservice/restQuote/"
           f"symbolType/symbol?symbols={sym}&requestMethod=itv&noform=1"
           "&partnerId=2&fund=1&exthrs=1&output=json")
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    q = r.json()["FormattedQuoteResult"]["FormattedQuote"][0]
    last = float(str(q["last"]).replace(",", ""))
    out = _empty()
    out["close"] = round(last, 2)
    out["date"] = q.get("last_time", "")
    if q.get("change"):
        try:
            out["change"] = round(float(q["change"]), 2)
        except ValueError:
            pass
    if q.get("change_pct"):
        try:
            out["pct_change"] = round(float(str(q["change_pct"]).rstrip("%")), 2)
        except ValueError:
            pass
    if out["change"] is None and out["pct_change"] is not None:
        out["change"] = round(last - last / (1 + out["pct_change"] / 100), 2)
    out["source"] = f"CNBC 期货实时（{q.get('name', sym)}）"
    return out


def _from_fred(name: str) -> Dict[str, Optional[float]]:
    series = FRED_SERIES[name]
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    rows = [row for row in csv.DictReader(io.StringIO(r.text))
            if row.get(series) not in (None, "", ".")]
    if not rows:
        raise ValueError("FRED 无有效数据")
    last, prev = rows[-1], rows[-2]
    close, prev_close = float(last[series]), float(prev[series])
    out = _empty()
    out.update({
        "date": last["observation_date"],
        "close": round(close, 2),
        "prev_close": round(prev_close, 2),
        "change": round(close - prev_close, 2),
        "pct_change": round((close - prev_close) / prev_close * 100, 2),
        "source": f"FRED {series} 现货日线（美元/桶）",
    })
    return out


def _from_stooq(name: str) -> Dict[str, Optional[float]]:
    sym = STOOQ_SYMBOLS[name]
    url = f"https://stooq.com/q/d/l/?s={sym}&i=d"
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    if not r.text.lstrip().startswith("Date"):
        raise ValueError("Stooq 返回非 CSV（可能触发浏览器校验）")
    rows = [row for row in csv.DictReader(io.StringIO(r.text))
            if row.get("Close") not in (None, "", "0")]
    if len(rows) < 1:
        raise ValueError("Stooq 无有效数据")
    last = rows[-1]
    out = _empty()
    out["date"] = last.get("Date")
    out["close"] = float(last["Close"])
    out["source"] = "Stooq 期货日线（美元/桶）"
    if len(rows) >= 2:
        prev_close = float(rows[-2]["Close"])
        out["prev_close"] = round(prev_close, 2)
        out["change"] = round(out["close"] - prev_close, 2)
        out["pct_change"] = round((out["close"] - prev_close) / prev_close * 100, 2)
    return out


def _one(name: str) -> Dict[str, Optional[float]]:
    errors = []
    for getter in (_from_cnbc, _from_fred, _from_stooq):
        try:
            return getter(name)
        except Exception as exc:  # 单个来源失败，尝试下一个
            errors.append(f"{getter.__name__}: {str(exc)[:120]}")
    return _empty("；".join(errors))


def snapshot() -> Dict[str, dict]:
    result = {name: _one(name) for name in CNBC_SYMBOLS}
    result["fetched_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    srcs = sorted({v.get("source") for v in result.values() if isinstance(v, dict) and v.get("source")})
    result["source"] = " / ".join(srcs) if srcs else "全部价格源不可用"
    return result
