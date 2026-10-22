"""Weekly recap: one summary per trading week, newest first."""
from __future__ import annotations

import datetime as dt

import pandas as pd

from .signals import frame_score, label_for


def _pct(a, b):
    return round((a / b - 1) * 100, 2) if b else None


def build(daily: pd.DataFrame, events: list[dict], signals_log: list[dict], iv_hist: list[dict],
          today: dt.date, weeks: int = 12) -> list[dict]:
    if daily.empty:
        return []
    d = daily.copy()
    d["date"] = [ts.date() for ts in d.index]
    d["week"] = [x - dt.timedelta(days=x.weekday()) for x in d["date"]]
    d["chg"] = d["Close"].pct_change() * 100
    ivmap = {h["date"]: h["iv"] for h in iv_hist}
    out = []
    groups = list(d.groupby("week"))
    for gi, (wk, g) in enumerate(groups):
        prev_close = float(groups[gi - 1][1]["Close"].iloc[-1]) if gi > 0 else float(g["Open"].iloc[0])
        close = float(g["Close"].iloc[-1])
        first_i = d.index.get_loc(g.index[0])
        prior = d.iloc[max(0, first_i - 20):first_i]
        vol_ratio = round(float(g["Volume"].mean() / prior["Volume"].mean()), 2) if len(prior) >= 5 and prior["Volume"].mean() else None
        last_i = d.index.get_loc(g.index[-1])
        score = round(frame_score(daily, last_i, "Daily")[0]) if last_i > 0 else 0
        best = g["chg"].idxmax() if g["chg"].notna().any() else None
        worst = g["chg"].idxmin() if g["chg"].notna().any() else None
        wk_end = wk + dt.timedelta(days=6)
        evs = [{"date": e["date"], "type": e["type"], "title": e["title"].split(" — ")[0]} for e in events
               if wk.isoformat() <= e["date"] <= wk_end.isoformat() and e["type"] != "opex"]
        sigs = [s for s in signals_log if wk.isoformat() <= s["time"][:10] <= wk_end.isoformat()]
        ivs = [ivmap[x.isoformat()] for x in g["date"] if x.isoformat() in ivmap]
        rec = {
            "week_of": wk.isoformat(), "end": g["date"].iloc[-1].isoformat(), "days": len(g),
            "in_progress": wk <= today <= wk_end and g["date"].iloc[-1].weekday() < 4,
            "open": round(float(g["Open"].iloc[0]), 2), "close": round(close, 2),
            "high": round(float(g["High"].max()), 2), "low": round(float(g["Low"].min()), 2),
            "change_pct": _pct(close, prev_close),
            "range_pct": round(float((g["High"].max() / g["Low"].min() - 1) * 100), 1),
            "best_day": {"date": best.date().isoformat(), "pct": round(float(g.loc[best, "chg"]), 2)} if best is not None else None,
            "worst_day": {"date": worst.date().isoformat(), "pct": round(float(g.loc[worst, "chg"]), 2)} if worst is not None else None,
            "volume_vs_prior": vol_ratio, "score_end": score, "label_end": label_for(score),
            "events": evs,
            "signals": [{"time": s["time"], "label": s["label"], "score": s["score"], "price": s["price"],
                         "after_5d": s.get("after_5d"), "right_5d": s.get("right_5d")} for s in sigs],
            "iv_start": round(ivs[0] * 100, 1) if ivs else None, "iv_end": round(ivs[-1] * 100, 1) if ivs else None,
        }
        rec["recap"] = _paragraph(rec)
        out.append(rec)
    return list(reversed(out))[:weeks]


def _paragraph(w: dict) -> str:
    wk = dt.date.fromisoformat(w["week_of"])
    chg = w["change_pct"]
    if w["in_progress"]:
        s = f"So far this week SPCX is {'up' if chg >= 0 else 'down'} {abs(chg):.1f}% at ${w['close']:.2f}"
    else:
        s = f"SPCX {'gained' if chg >= 0 else 'lost'} {abs(chg):.1f}% for the week, closing at ${w['close']:.2f}"
    s += f", trading between ${w['low']:.2f} and ${w['high']:.2f} (a {w['range_pct']:.0f}% range)."
    parts = [s]
    b, wo = w["best_day"], w["worst_day"]
    if b and wo and w["days"] > 1:
        bd, wd = dt.date.fromisoformat(b["date"]), dt.date.fromisoformat(wo["date"])
        if b["pct"] > 0 and wo["pct"] < 0:
            parts.append(f"The best day was {bd:%A} ({b['pct']:+.1f}%) and the worst was {wd:%A} ({wo['pct']:+.1f}%).")
        elif b["pct"] > 0:
            parts.append(f"Every day finished higher; the biggest gain came {bd:%A} ({b['pct']:+.1f}%).")
        else:
            parts.append(f"Every day finished lower; the biggest drop came {wd:%A} ({wo['pct']:+.1f}%).")
    v = w["volume_vs_prior"]
    if v and v >= 1.4:
        parts.append(f"Trading was busy, at {v:.1f}× the usual volume.")
    elif v and v <= 0.7:
        parts.append("Trading was quieter than usual.")
    if w["events"]:
        names = [e["title"].split(" (")[0] for e in w["events"][:3]]
        parts.append(("Events this week: " if w["in_progress"] else "Events: ") + "; ".join(names) + ".")
    if w["signals"]:
        n = len(w["signals"])
        parts.append(f"{n} strong signal{'s' if n > 1 else ''} appeared ({', '.join(s['label'] for s in w['signals'][:3])}).")
    parts.append(f"The daily-chart score {'ended' if not w['in_progress'] else 'stands'} at {w['score_end']:+d} ({w['label_end'].lower()}).")
    if w["iv_start"] and w["iv_end"] and abs(w["iv_end"] - w["iv_start"]) >= 3:
        parts.append(f"Option prices {'rose' if w['iv_end'] > w['iv_start'] else 'fell'}: implied volatility went from {w['iv_start']:.0f}% to {w['iv_end']:.0f}%.")
    return " ".join(parts)
