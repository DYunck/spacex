"""Option math (Black-Scholes Greeks) and option-chain analysis."""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

RATE = 0.04  # approximate risk-free rate


def _ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _npdf(x):
    return math.exp(-x * x / 2) / math.sqrt(2 * math.pi)


def bs_price(S, K, T, iv, kind, r=RATE):
    if T <= 0 or iv <= 0:
        return max(0.0, (S - K) if kind == "call" else (K - S))
    d1 = (math.log(S / K) + (r + iv * iv / 2) * T) / (iv * math.sqrt(T))
    d2 = d1 - iv * math.sqrt(T)
    if kind == "call":
        return S * _ncdf(d1) - K * math.exp(-r * T) * _ncdf(d2)
    return K * math.exp(-r * T) * _ncdf(-d2) - S * _ncdf(-d1)


def bs_greeks(S, K, T, iv, kind, r=RATE):
    if T <= 0 or iv <= 0 or S <= 0 or K <= 0:
        return {"delta": None, "theta": None, "gamma": None, "vega": None}
    sq = math.sqrt(T)
    d1 = (math.log(S / K) + (r + iv * iv / 2) * T) / (iv * sq)
    d2 = d1 - iv * sq
    gamma = _npdf(d1) / (S * iv * sq)
    vega = S * _npdf(d1) * sq / 100
    if kind == "call":
        delta = _ncdf(d1)
        theta = (-S * _npdf(d1) * iv / (2 * sq) - r * K * math.exp(-r * T) * _ncdf(d2)) / 365
    else:
        delta = _ncdf(d1) - 1
        theta = (-S * _npdf(d1) * iv / (2 * sq) + r * K * math.exp(-r * T) * _ncdf(-d2)) / 365
    return {"delta": delta, "theta": theta, "gamma": gamma, "vega": vega}


def implied_vol(price, S, K, T, kind):
    """Back out implied volatility from an option price (bisection). None if impossible."""
    if price is None or price <= 0 or T <= 0:
        return None
    intrinsic = max(0.0, (S - K) if kind == "call" else (K - S))
    if price <= intrinsic + 0.005:
        return None
    lo, hi = 0.01, 5.0
    if bs_price(S, K, T, hi, kind) < price:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        if bs_price(S, K, T, mid, kind) > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def prepare_chain(chain: pd.DataFrame, spot: float, today: dt.date) -> pd.DataFrame:
    if chain is None or chain.empty:
        return pd.DataFrame()
    c = chain.copy()
    for col in ("bid", "ask", "lastPrice", "volume", "openInterest", "impliedVolatility", "strike"):
        c[col] = pd.to_numeric(c.get(col), errors="coerce").fillna(0)
    c["dte"] = c["expiry"].map(lambda e: (dt.date.fromisoformat(e) - today).days)
    c["mid"] = np.where((c["bid"] > 0) & (c["ask"] > 0), (c["bid"] + c["ask"]) / 2, c["lastPrice"])
    c["spread_pct"] = np.where((c["bid"] > 0) & (c["mid"] > 0), (c["ask"] - c["bid"]) / c["mid"] * 100, np.nan)
    # Yahoo's own IV is unreliable outside market hours, so calculate it from the option's price.
    own = [implied_vol(r.mid, spot, r.strike, max(r.dte, 0.5) / 365, r.type) for r in c.itertuples()]
    c["impliedVolatility"] = [o if o is not None else (y if y > 0.05 else 0.0) for o, y in zip(own, c["impliedVolatility"])]
    g = [bs_greeks(spot, r.strike, max(r.dte, 0.5) / 365, r.impliedVolatility, r.type) for r in c.itertuples()]
    for k in ("delta", "theta", "gamma", "vega"):
        c[k] = [x[k] for x in g]
    c["breakeven"] = np.where(c["type"] == "call", c["strike"] + c["mid"], c["strike"] - c["mid"])
    return c


def atm_iv(c: pd.DataFrame, spot: float, min_dte: int = 7) -> tuple[float | None, str | None]:
    """Average call+put IV at the strike nearest the stock price, nearest expiry >= min_dte."""
    if c.empty:
        return None, None
    usable = c[(c["dte"] >= min_dte) & (c["impliedVolatility"] > 0.01)]
    if usable.empty:
        usable = c[c["impliedVolatility"] > 0.01]
    if usable.empty:
        return None, None
    exp = usable.sort_values("dte")["expiry"].iloc[0]
    e = usable[usable["expiry"] == exp]
    k = e.iloc[(e["strike"] - spot).abs().argsort()[:1]]["strike"].iloc[0]
    iv = e[e["strike"] == k]["impliedVolatility"].mean()
    return float(iv), exp


def expected_move(c: pd.DataFrame, spot: float, by_date: dt.date | None) -> dict | None:
    """ATM straddle price for the first expiry on/after by_date = market's implied +/- move."""
    if c.empty:
        return None
    cand = c if by_date is None else c[c["expiry"] >= by_date.isoformat()]
    if cand.empty:
        return None
    exp = sorted(cand["expiry"].unique())[0]
    e = cand[cand["expiry"] == exp]
    k = e.iloc[(e["strike"] - spot).abs().argsort()[:1]]["strike"].iloc[0]
    call = e[(e["strike"] == k) & (e["type"] == "call")]["mid"]
    put = e[(e["strike"] == k) & (e["type"] == "put")]["mid"]
    if call.empty or put.empty:
        return None
    move = float(call.iloc[0] + put.iloc[0])
    return {"expiry": exp, "strike": float(k), "dollars": round(move, 2), "pct": round(move / spot * 100, 1)}


def flow(c: pd.DataFrame) -> dict:
    if c.empty:
        return {}
    calls, puts = c[c["type"] == "call"], c[c["type"] == "put"]
    cv, pv = calls["volume"].sum(), puts["volume"].sum()
    coi, poi = calls["openInterest"].sum(), puts["openInterest"].sum()
    unusual = c[(c["volume"] >= 500) & (c["volume"] > 2 * c["openInterest"].clip(lower=1))]
    unusual = unusual.sort_values("volume", ascending=False).head(8)
    return {
        "call_volume": int(cv), "put_volume": int(pv),
        "pc_volume": round(pv / cv, 2) if cv else None,
        "pc_open_interest": round(poi / coi, 2) if coi else None,
        "unusual": [{
            "contract": f"{r.expiry} {r.strike:g} {r.type}", "volume": int(r.volume),
            "open_interest": int(r.openInterest), "mid": round(r.mid, 2),
        } for r in unusual.itertuples()],
    }


def suggest(c: pd.DataFrame, kind: str, cfg: dict, events: list[dict], today: dt.date) -> list[dict]:
    s = cfg["suggest"]
    if c.empty:
        return []
    f = c[(c["type"] == kind) & (c["dte"] >= s["min_days_to_expiry"]) & (c["dte"] <= s["max_days_to_expiry"])
          & (c["openInterest"] >= s["min_open_interest"]) & (c["spread_pct"] <= s["max_spread_pct"])
          & (c["mid"] > 0.05) & c["delta"].notna()]
    if f.empty:  # loosen the window if nothing fits
        f = c[(c["type"] == kind) & (c["dte"] >= 7) & (c["mid"] > 0.05) & c["delta"].notna()
              & (c["spread_pct"] <= s["max_spread_pct"] * 1.5)]
    if f.empty:
        return []
    f = f.assign(dist=(f["delta"].abs() - s["target_delta"]).abs())
    picks = f.sort_values(["dist", "spread_pct"]).groupby("expiry").head(1).sort_values("dte").head(3)
    out = []
    for r in picks.itertuples():
        exp = dt.date.fromisoformat(r.expiry)
        inside = [e["title"] for e in events if today <= dt.date.fromisoformat(e["date"]) <= exp
                  and e["type"] in ("earnings", "lockup")]
        out.append({
            "contract": f"SPCX {exp:%b %d %Y} ${r.strike:g} {kind}",
            "expiry": r.expiry, "strike": float(r.strike), "dte": int(r.dte),
            "mid": round(r.mid, 2), "cost": round(r.mid * 100, 0),
            "bid": round(r.bid, 2), "ask": round(r.ask, 2), "spread_pct": round(r.spread_pct, 1),
            "delta": round(r.delta, 2), "theta_per_day": round(r.theta * 100, 2),
            "iv": round(r.impliedVolatility * 100, 1), "breakeven": round(r.breakeven, 2),
            "open_interest": int(r.openInterest), "max_loss": round(r.mid * 100, 0),
            "events_before_expiry": inside,
        })
    return out


def compact_chain(c: pd.DataFrame, spot: float, width: float = 0.35) -> list[dict]:
    """Trimmed chain for the payoff calculator: strikes within +/-35% of the price."""
    if c.empty:
        return []
    f = c[(c["strike"] >= spot * (1 - width)) & (c["strike"] <= spot * (1 + width)) & (c["mid"] > 0)]
    return [{"e": r.expiry, "k": float(r.strike), "t": r.type[0], "b": round(r.bid, 2), "a": round(r.ask, 2),
             "m": round(r.mid, 2), "iv": round(r.impliedVolatility, 4), "oi": int(r.openInterest)}
            for r in f.sort_values(["expiry", "type", "strike"]).itertuples()]
