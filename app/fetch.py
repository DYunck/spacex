"""Download SPCX price history and option chains (Yahoo Finance via yfinance).

Also provides a --sample mode that generates realistic fake data so the
dashboard can be tested without network access.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

NY = "America/New_York"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    if df.index.tz is None:
        df.index = df.index.tz_localize(NY)
    else:
        df.index = df.index.tz_convert(NY)
    return df


def fetch_live(cfg: dict) -> dict:
    import yfinance as yf

    sym = cfg["ticker"]
    t = yf.Ticker(sym)
    daily = _clean(t.history(start=cfg["ipo_date"], interval="1d", auto_adjust=False))
    hourly = _clean(t.history(period="60d", interval="60m", auto_adjust=False))

    context = {}
    for c in cfg.get("context_tickers", {}):
        try:
            context[c] = _clean(yf.Ticker(c).history(period="6mo", interval="1d", auto_adjust=False))
        except Exception as e:  # context is nice-to-have
            print(f"context {c} failed: {e}")
            context[c] = _clean(None)

    chains = []
    try:
        expiries = list(t.options)[: cfg.get("option_expirations", 6)]
    except Exception as e:
        print(f"option expiries failed: {e}")
        expiries = []
    for exp in expiries:
        try:
            oc = t.option_chain(exp)
        except Exception as e:
            print(f"chain {exp} failed: {e}")
            continue
        for kind, frame in (("call", oc.calls), ("put", oc.puts)):
            f = frame.copy()
            f["type"] = kind
            f["expiry"] = exp
            chains.append(f)
    chain = pd.concat(chains, ignore_index=True) if chains else pd.DataFrame()
    return {"daily": daily, "hourly": hourly, "context": context, "chain": chain, "source": "Yahoo Finance"}


# ---------------------------------------------------------------- sample data

def _sample_path(n: int, start: float, vol: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, vol, n)
    # mimic the real shape: pop, long slide, recovery
    drift = np.concatenate([
        np.full(n // 6, 0.02), np.full(n // 3, -0.012), np.full(n - n // 6 - n // 3, 0.006)
    ])[:n]
    return start * np.exp(np.cumsum(rets + drift))


def fetch_sample(cfg: dict) -> dict:
    end = pd.Timestamp.now(tz=NY).normalize().tz_localize(None)
    days = pd.bdate_range(cfg["ipo_date"], end).tz_localize(NY)
    n = len(days)
    close = _sample_path(n, cfg["ipo_price"] * 1.15, 0.035, 1)
    rng = np.random.default_rng(2)
    openp = close * (1 + rng.normal(0, 0.01, n))
    high = np.maximum(openp, close) * (1 + abs(rng.normal(0, 0.015, n)))
    low = np.minimum(openp, close) * (1 - abs(rng.normal(0, 0.015, n)))
    vol = rng.integers(40e6, 120e6, n)
    daily = pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": vol}, index=days)

    hrs = []
    for d in days[-40:]:
        for h in range(7):
            hrs.append(d + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(hours=h))
    hidx = pd.DatetimeIndex(hrs)
    hclose = _sample_path(len(hidx), close[-40], 0.012, 3)
    hclose *= close[-1] / hclose[-1]
    hopen = np.roll(hclose, 1); hopen[0] = hclose[0]
    hourly = pd.DataFrame({
        "Open": hopen, "High": np.maximum(hopen, hclose) * 1.004, "Low": np.minimum(hopen, hclose) * 0.996,
        "Close": hclose, "Volume": rng.integers(4e6, 18e6, len(hidx)),
    }, index=hidx)

    context = {}
    for i, c in enumerate(cfg.get("context_tickers", {})):
        base = {"QQQ": 610, "^VIX": 18, "TSLA": 420}.get(c, 100)
        cd = pd.bdate_range(end - pd.Timedelta(days=180), end).tz_localize(NY)
        cc = _sample_path(len(cd), base, 0.015, 10 + i)
        context[c] = pd.DataFrame({"Open": cc, "High": cc, "Low": cc, "Close": cc, "Volume": 0}, index=cd)

    spot = close[-1]
    rows = []
    today = end.date()
    exps = []
    d = today
    while len(exps) < cfg.get("option_expirations", 6):
        d += dt.timedelta(days=1)
        if d.weekday() == 4:
            exps.append(d)
    exps = exps[:2] + [x for x in _third_fridays(today, 6) if x > exps[1]][:4]
    from .options import bs_price
    for e in exps:
        T = max((e - today).days, 1) / 365
        for k in np.arange(round(spot * 0.6 / 5) * 5, spot * 1.4, 5):
            for kind in ("call", "put"):
                iv = 0.62 + 0.25 * abs(math.log(k / spot)) + (0.08 if (e - today).days < 10 else 0)
                p = bs_price(spot, k, T, iv, kind)
                spr = max(0.05, p * 0.04)
                oi = int(max(0, 8000 * math.exp(-abs(k - spot) / (spot * 0.12)) * rng.uniform(0.5, 1.5)))
                rows.append({
                    "contractSymbol": f"SPCX{e:%y%m%d}{kind[0].upper()}{int(k*1000):08d}",
                    "strike": float(k), "lastPrice": p, "bid": max(0, p - spr / 2), "ask": p + spr / 2,
                    "volume": int(oi * rng.uniform(0.05, 0.6)), "openInterest": oi,
                    "impliedVolatility": iv, "type": kind, "expiry": e.isoformat(),
                })
    return {"daily": daily, "hourly": hourly, "context": context, "chain": pd.DataFrame(rows), "source": "SAMPLE DATA (not real)"}


def _third_fridays(start: dt.date, count: int) -> list[dt.date]:
    out = []
    y, m = start.year, start.month
    while len(out) < count:
        first = dt.date(y, m, 1)
        fri = first + dt.timedelta(days=(4 - first.weekday()) % 7 + 14)
        if fri >= start:
            out.append(fri)
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out
