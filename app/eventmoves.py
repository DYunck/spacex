"""How SPCX actually moved around past earnings and lockup dates, vs. what options priced in."""
from __future__ import annotations

import datetime as dt

import pandas as pd


def _close_on_or_before(closes: pd.Series, d: dt.date):
    s = closes[closes.index.date <= d]
    return (s.index[-1].date(), float(s.iloc[-1])) if len(s) else (None, None)


def _close_after(closes: pd.Series, d: dt.date, n: int = 1):
    s = closes[closes.index.date > d]
    return (s.index[n - 1].date(), float(s.iloc[n - 1])) if len(s) >= n else (None, None)


def history(daily: pd.DataFrame, events: list[dict], em_hist: dict, today: dt.date) -> list[dict]:
    closes = daily["Close"]
    out = []
    for e in events:
        if e["type"] not in ("earnings", "lockup"):
            continue
        d = dt.date.fromisoformat(e["date"])
        if d > today:
            continue
        if e["type"] == "earnings":  # reported after the close on day d
            _, before = _close_on_or_before(closes, d)
            _, after1 = _close_after(closes, d, 1)
            _, after3 = _close_after(closes, d, 3)
        else:  # shares unlock at the open on day d
            _, before = _close_on_or_before(closes, d - dt.timedelta(days=1))
            _, after1 = _close_on_or_before(closes, d) if (closes.index.date >= d).any() else (None, None)
            _, after3 = _close_after(closes, d, 2)
        if before is None or after1 is None:
            continue
        m1 = (after1 / before - 1) * 100
        m3 = (after3 / before - 1) * 100 if after3 else None
        em = em_hist.get(e["date"])
        implied = em["pct"] if em else None
        out.append({
            "date": e["date"], "type": e["type"], "title": e["title"].split(" — ")[0],
            "move_1d_pct": round(m1, 1), "move_3d_pct": round(m3, 1) if m3 is not None else None,
            "implied_pct": implied,
            "vs_implied": (None if implied is None else ("bigger than priced in" if abs(m1) > implied else "smaller than priced in")),
        })
    return sorted(out, key=lambda x: x["date"], reverse=True)


def summarize(rows: list[dict]) -> dict:
    with_imp = [r for r in rows if r["implied_pct"] is not None]
    earn = [r for r in rows if r["type"] == "earnings"]
    lock = [r for r in rows if r["type"] == "lockup"]
    avg = lambda xs: round(sum(abs(x["move_1d_pct"]) for x in xs) / len(xs), 1) if xs else None
    return {
        "earnings_count": len(earn), "earnings_avg_abs_move": avg(earn),
        "lockup_count": len(lock), "lockup_avg_move": round(sum(x["move_1d_pct"] for x in lock) / len(lock), 1) if lock else None,
        "priced_in_compared": len(with_imp),
        "smaller_than_priced": sum(1 for r in with_imp if r["vs_implied"] == "smaller than priced in"),
    }
