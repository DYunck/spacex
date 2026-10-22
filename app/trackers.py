"""Starship flight tracker, insider-selling (lockup) tracker and analyst summary."""
from __future__ import annotations

import datetime as dt

import pandas as pd

NY = "America/New_York"


# ---------------------------------------------------------------- Starship flights

def _reaction(daily: pd.DataFrame, when: pd.Timestamp):
    """Stock reaction to something that happened at `when` (NY time).
    During or before market hours on a trading day -> that day's close vs the prior close.
    After the close or on a non-trading day -> the next trading day's close vs the last close before it."""
    closes = daily["Close"]
    dates = [ts.date() for ts in closes.index]
    d = when.date()
    after_close = when.hour * 60 + when.minute >= 16 * 60
    if d in dates and not after_close:
        i = dates.index(d)
    else:
        later = [k for k, x in enumerate(dates) if x > d]
        if not later:
            return None
        i = later[0]
    if i == 0:
        return None
    base = float(closes.iloc[i - 1])
    r1 = (float(closes.iloc[i]) / base - 1) * 100
    r2 = (float(closes.iloc[i + 1]) / base - 1) * 100 if i + 1 < len(closes) else None
    return {"day": dates[i].isoformat(), "move_pct": round(r1, 2), "move_2d_pct": round(r2, 2) if r2 is not None else None}


def _result(status: str) -> str:
    s = (status or "").lower()
    if "partial" in s:
        return "Partial failure"
    if "fail" in s:
        return "Failure"
    if "success" in s:
        return "Success"
    return status or "Unknown"


def starship(flights: list[dict], daily: pd.DataFrame, upcoming: list[dict], ipo_date: str) -> dict:
    ipo = dt.date.fromisoformat(ipo_date)
    rows = []
    for f in flights or []:
        if not f.get("net"):
            continue
        when = pd.Timestamp(f["net"]).tz_convert(NY)
        row = {"date": when.date().isoformat(), "time_et": when.strftime("%-I:%M %p ET"), "name": f["name"].split("| ")[-1].strip() or f["name"],
               "result": _result(f.get("status")), "failreason": f.get("failreason") or "",
               "description": (f.get("description") or "")[:240], "before_ipo": when.date() < ipo, "reaction": None}
        if not row["before_ipo"]:
            row["reaction"] = _reaction(daily, when)
        rows.append(row)
    rows.sort(key=lambda r: r["date"], reverse=True)
    since = [r for r in rows if not r["before_ipo"]]

    def avg(rs):
        xs = [r["reaction"]["move_pct"] for r in rs if r["reaction"]]
        return round(sum(xs) / len(xs), 2) if xs else None
    ok = [r for r in since if r["result"] == "Success"]
    bad = [r for r in since if r["result"] in ("Failure", "Partial failure")]
    nxt = next((u for u in upcoming if "starship" in (u.get("name", "") + u.get("rocket", "")).lower()), None)
    return {
        "flights": rows[:20],
        "summary": {"since_ipo": len(since), "successes": len(ok), "failures": len(bad),
                    "avg_move_success": avg(ok), "avg_move_failure": avg(bad), "avg_move_all": avg(since)},
        "next": ({"name": nxt["name"].split("| ")[-1], "net": nxt.get("net"), "status": nxt.get("status", "")} if nxt else None),
    }


# ---------------------------------------------------------------- insider selling / lockups

def lockups(cfg: dict, shares: dict | None, event_moves: list[dict], today: dt.date) -> dict:
    total_m = (shares or {}).get("outstanding")
    total_m = total_m / 1e6 if total_m else float(cfg.get("total_shares_m", 13200))
    ipo_float = float(cfg.get("ipo_float_m", 0))
    moves = {m["date"]: m for m in event_moves if m.get("type") == "lockup"}
    rows, released, upcoming_std = [], 0.0, 0.0
    for u in cfg.get("unlocks", []):
        d = u.get("date")
        sh = u.get("shares_m")
        status = "date TBD" if not d else ("released" if d <= today.isoformat() else "upcoming")
        if status == "released" and sh:
            released += sh
        elif status == "upcoming" and sh and u.get("group") == "standard":
            upcoming_std += sh
        m = moves.get(d) if d else None
        rows.append({"date": d, "label": u.get("label"), "shares_m": sh, "group": u.get("group"), "note": u.get("note", ""),
                     "pct_of_company": round(sh / total_m * 100, 1) if sh else None, "status": status,
                     "days": (dt.date.fromisoformat(d) - today).days if d else None,
                     "move_pct": m["move_1d_pct"] if m else None, "move_3d_pct": m.get("move_3d_pct") if m else None})
    tradable = ipo_float + released
    extended = float(cfg.get("extended_group_m", 0))
    locked_other = max(0.0, total_m - tradable - upcoming_std - extended)
    nxt = next((r for r in rows if r["status"] == "upcoming"), None)
    past_moves = [r["move_pct"] for r in rows if r["move_pct"] is not None]
    yahoo_float = (shares or {}).get("float")
    return {
        "total_m": round(total_m, 1), "tradable_m": round(tradable, 1), "tradable_pct": round(tradable / total_m * 100, 1),
        "upcoming_standard_m": round(upcoming_std, 1), "extended_m": round(extended, 1), "other_locked_m": round(locked_other, 1),
        "yahoo_float_m": round(yahoo_float / 1e6, 1) if yahoo_float else None,
        "next": nxt, "rows": rows,
        "past_unlocks": len(past_moves), "past_up": sum(1 for x in past_moves if x > 0),
        "past_avg_move": round(sum(past_moves) / len(past_moves), 2) if past_moves else None,
        "after_dec8_pct": round((tradable + upcoming_std) / total_m * 100, 1),
    }


# ---------------------------------------------------------------- analysts

def analysts(a: dict | None, price: float) -> dict | None:
    if not a:
        return None
    t = a.get("targets") or {}
    mean = t.get("mean") or t.get("median")
    out = dict(a)
    out["price"] = round(price, 2)
    out["upside_mean_pct"] = round((mean / price - 1) * 100, 1) if mean else None
    for k in ("low", "high"):
        out[f"upside_{k}_pct"] = round((t[k] / price - 1) * 100, 1) if t.get(k) else None
    words = {"strong_buy": "Strong buy", "buy": "Buy", "hold": "Hold", "underperform": "Underperform", "sell": "Sell",
             "strong_sell": "Strong sell", "none": None}
    out["rating_text"] = words.get((a.get("rating_key") or "").lower(), (a.get("rating_key") or "").replace("_", " ").title() or None)
    return out
