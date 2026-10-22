"""Main job: fetch data, analyze, write dashboard data. Sends nothing to anyone.

    python -m app.run              # live data
    python -m app.run --sample     # fake data for testing
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path

import pandas as pd
import yaml

from . import backtest, eventmoves, fetch, indicators as ind, options as opt, signals, summary, weekly

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "data"
NY = "America/New_York"


# ------------------------------------------------------------------ helpers

def _num(x, nd=2):
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(f) or math.isinf(f) else round(f, nd)


def _load_json(p: Path, default):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def _third_fridays(start: dt.date, n: int) -> list[dt.date]:
    return fetch._third_fridays(start, n)


def load_events(today: dt.date) -> list[dict]:
    raw = yaml.safe_load((ROOT / "data" / "events.yaml").read_text()) or {}
    ev = [dict(e, date=str(e["date"])) for e in raw.get("events", []) if e.get("date")]
    for f in _third_fridays(today, 3):
        ev.append({"date": f.isoformat(), "type": "opex", "title": "Monthly options expiration", "verified": True})
    return sorted(ev, key=lambda e: e["date"])


def compare_series(daily: pd.DataFrame, context: dict) -> list[dict]:
    """SPCX, Tesla and Nasdaq-100 closes on SPCX trading days (the page rescales to % change)."""
    cols = {"s": daily["Close"]}
    for sym, key in (("TSLA", "tsla"), ("QQQ", "qqq")):
        c = context.get(sym)
        if c is not None and not c.empty:
            cols[key] = c["Close"]
    df = pd.DataFrame({k: v.groupby(v.index.date).last() for k, v in cols.items()}).dropna(subset=["s"]).ffill()
    return [{"t": d.isoformat(), **{k: _num(r[k]) for k in df.columns}} for d, r in df.iterrows()]


def notable_launch(x: dict) -> bool:
    text = f"{x.get('name', '')} {x.get('rocket', '')} {x.get('mission_type', '')}".lower()
    return any(k in text for k in ("starship", "falcon heavy", "crew", "human", "dragon"))


def launch_events(launches: list[dict], today: dt.date) -> list[dict]:
    """Big launches (Starship, Falcon Heavy, crewed) go into the event calendar."""
    out = []
    for x in launches:
        if not notable_launch(x):
            continue
        d = pd.Timestamp(x["net"]).tz_convert(NY).date()
        if (d - today).days > 60:
            continue
        name = x["name"].replace(" Block 5", "").replace(" | ", ": ")
        conf = "" if x.get("status") == "Go" else f" ({x.get('status_name') or 'date not final'})"
        out.append({"date": d.isoformat(), "type": "launch", "title": f"{name} launch{conf}",
                    "verified": x.get("status") == "Go"})
    return out


def bars(df: pd.DataFrame, intraday: bool, cols=("sma20", "sma50", "bb_up", "bb_low")) -> list[dict]:
    out = []
    for ts, r in df.iterrows():
        t = int(pd.Timestamp(ts.tz_localize(None)).timestamp()) if intraday else ts.strftime("%Y-%m-%d")
        row = {"t": t, "o": _num(r.Open), "h": _num(r.High), "l": _num(r.Low), "c": _num(r.Close), "v": int(r.Volume)}
        for c in cols + ("rsi", "macd_hist"):
            row[c] = _num(r.get(c))
        out.append(row)
    return out


def snapshot(df: pd.DataFrame) -> dict:
    r = df.iloc[-1]
    return {k: _num(r.get(k)) for k in ("Close", "sma20", "sma50", "rsi", "macd", "macd_signal", "macd_hist",
                                         "bb_up", "bb_low", "atr", "rvol20")} | {
        "volume_vs_avg": _num(r["Volume"] / r["vol_avg20"]) if r.get("vol_avg20") else None}


# ------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true")
    ap.add_argument("--mode", choices=["auto", "intraday", "summary"], default="auto")
    a = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    now = pd.Timestamp.now(tz=NY)
    today = now.date()
    OUT.mkdir(parents=True, exist_ok=True)

    mode = a.mode
    if mode == "auto":
        mins = now.hour * 60 + now.minute
        mode = "summary" if mins >= 16 * 60 + 10 or mins < 9 * 60 + 30 else "intraday"

    data = fetch.fetch_sample(cfg) if a.sample else fetch.fetch_live(cfg)
    daily, hourly = data["daily"], data["hourly"]
    # Yahoo sometimes leaves today's daily bar out; build it from today's hourly bars.
    if not hourly.empty and not daily.empty and hourly.index[-1].date() > daily.index[-1].date():
        day = hourly.index[-1].date()
        hb = hourly[hourly.index.date == day]
        today_bar = pd.DataFrame({"Open": [hb["Open"].iloc[0]], "High": [hb["High"].max()], "Low": [hb["Low"].min()],
                                  "Close": [hb["Close"].iloc[-1]], "Volume": [hb["Volume"].sum()]},
                                 index=pd.DatetimeIndex([pd.Timestamp(day, tz=NY)]))
        daily = pd.concat([daily, today_bar])
    if daily.empty:
        raise SystemExit("No daily data returned — check the ticker in config.yaml")

    daily = ind.add_all(daily, 252)
    hourly = ind.add_all(hourly, 252 * 6.5) if not hourly.empty else hourly
    spot = float(hourly["Close"].iloc[-1]) if not hourly.empty and hourly.index[-1] > daily.index[-1] else float(daily["Close"].iloc[-1])
    prev_close = float(daily["Close"].iloc[-2]) if len(daily) > 1 else spot
    if not hourly.empty and hourly.index[-1].date() == daily.index[-1].date() and len(daily) > 1:
        prev_close = float(daily["Close"].iloc[-2])

    # Upcoming SpaceX launches (cached so a failed fetch keeps the last good list)
    launches = data.get("launches")
    if launches is None:
        launches = _load_json(OUT / "launches.json", {}).get("launches", [])
    elif not a.sample:
        (OUT / "launches.json").write_text(json.dumps({"fetched": now.isoformat(timespec="minutes"), "launches": launches}, indent=1))
    launches = [x for x in launches if x.get("net") and pd.Timestamp(x["net"]).tz_convert(NY).date() >= today]
    news = data.get("news")
    if news is None:
        news = _load_json(OUT / "news.json", [])
    elif news and not a.sample:
        (OUT / "news.json").write_text(json.dumps(news, indent=1))

    events = load_events(today) + launch_events(launches, today)
    events.sort(key=lambda e: e["date"])
    upcoming = [e for e in events if e["date"] >= today.isoformat()]
    big = [e for e in upcoming if e["type"] in ("earnings", "lockup")]
    next_big = big[0] if big else None
    days_to_big = (dt.date.fromisoformat(next_big["date"]) - today).days if next_big else None

    # ---- options
    chain = opt.prepare_chain(data["chain"], spot, today)
    iv, iv_exp = opt.atm_iv(chain, spot)
    iv_hist = _load_json(OUT / "iv_history.json", [])
    if iv and not a.sample and mode == "intraday":  # only record IV from live market prices
        iv_hist = [h for h in iv_hist if h["date"] != today.isoformat()] + [{"date": today.isoformat(), "iv": round(iv, 4)}]
        iv_hist = iv_hist[-400:]
    hist_vals = [h["iv"] for h in iv_hist[-252:]]
    iv_rank = None
    if iv and len(hist_vals) >= 20 and max(hist_vals) > min(hist_vals):
        iv_rank = (iv - min(hist_vals)) / (max(hist_vals) - min(hist_vals)) * 100
    rv = _num(daily["rvol20"].iloc[-1], 4)

    em_date = dt.date.fromisoformat(next_big["date"]) if next_big and days_to_big is not None and days_to_big <= 45 else None
    exp_move = opt.expected_move(chain, spot, em_date)
    flow = opt.flow(chain)

    # Remember the priced-in move before each earnings/lockup, to compare with what actually happened.
    em_hist = _load_json(OUT / "expected_moves.json", {})
    if exp_move and next_big and em_date and mode == "intraday" and not a.sample:
        before_event = today < em_date or (today == em_date and next_big["type"] == "earnings")
        if before_event:
            em_hist[next_big["date"]] = {"pct": exp_move["pct"], "dollars": exp_move["dollars"],
                                         "expiry": exp_move["expiry"], "recorded": now.isoformat(timespec="minutes")}

    # ---- signals
    direction = signals.direction(daily, hourly)
    vol = signals.volatility_verdict(iv, rv, iv_rank, days_to_big)
    stance = signals.stance(direction["score"], vol["verdict"])
    calls = opt.suggest(chain, "call", cfg, events, today)
    puts = opt.suggest(chain, "put", cfg, events, today)

    # ---- strong-signal log + outcomes (recorded for the dashboard; nothing is sent)
    state = _load_json(OUT / "state.json", {})
    log = _load_json(OUT / "signals.json", [])
    closes = daily["Close"]
    for e in log:
        if e.get("price") and e.get("direction"):
            after = closes[closes.index.date > dt.date.fromisoformat(e["time"][:10])]
            for n in (1, 5, 10):
                key = f"after_{n}d"
                if e.get(key) is None and len(after) >= n:
                    ch = (float(after.iloc[n - 1]) / e["price"] - 1) * 100
                    e[key] = round(ch, 2)
                    e[f"right_{n}d"] = (ch > 0) == (e["direction"] == "up")

    score, label = direction["score"], direction["label"]
    strong = abs(score) >= cfg["signal_min_score"]
    new_signal = False
    if mode == "intraday" and strong and state.get("last_signal_label") != label and not a.sample:
        log.append({"time": now.isoformat(timespec="minutes"), "label": label, "score": score,
                    "price": round(spot, 2), "direction": "up" if score > 0 else "down",
                    "headline": stance["action"]})
        state["last_signal_label"] = label
        new_signal = True
    if not strong and abs(score) < cfg["signal_min_score"] * 0.5:
        state["last_signal_label"] = None  # re-arm once things calm down
    log = log[-300:]

    graded = [e for e in log if e.get("right_5d") is not None]
    track = {"signals": len(log), "graded_5d": len(graded),
             "right_5d_pct": round(sum(e["right_5d"] for e in graded) / len(graded) * 100) if graded else None}

    # ---- context
    ctx = {}
    for sym, name in cfg.get("context_tickers", {}).items():
        d = data["context"].get(sym)
        if d is not None and len(d) > 1:
            ctx[sym] = {"name": name, "last": _num(d["Close"].iloc[-1]),
                        "change_pct": _num((d["Close"].iloc[-1] / d["Close"].iloc[-2] - 1) * 100),
                        "change_20d_pct": _num((d["Close"].iloc[-1] / d["Close"].iloc[max(0, len(d) - 21)] - 1) * 100)}
    if "TSLA" in data["context"] and len(data["context"]["TSLA"]) > 30:
        j = pd.concat([daily["Close"].pct_change(), data["context"]["TSLA"]["Close"].pct_change()], axis=1, join="inner").dropna().tail(60)
        if len(j) > 20:
            ctx["TSLA"]["corr_60d"] = _num(j.corr().iloc[0, 1])

    result = {
        "generated": now.isoformat(timespec="minutes"), "mode": mode, "source": data["source"],
        "ticker": cfg["ticker"], "ipo_price": cfg["ipo_price"],
        "price": round(spot, 2), "prev_close": round(prev_close, 2),
        "change_pct": round((spot / prev_close - 1) * 100, 2),
        "high_since_ipo": _num(daily["High"].max()), "low_since_ipo": _num(daily["Low"].min()),
        "direction": direction, "volatility": vol | {"atm_iv": _num(iv * 100 if iv else None, 1), "atm_iv_expiry": iv_exp,
                                                      "realized_vol": _num(rv * 100 if rv else None, 1),
                                                      "iv_rank": _num(iv_rank, 0), "iv_history_days": len(hist_vals)},
        "stance": stance, "expected_move": exp_move, "flow": flow,
        "suggestions": {"calls": calls, "puts": puts},
        "levels": ind.support_resistance(daily, cfg["ipo_price"]),
        "daily_snapshot": snapshot(daily), "hourly_snapshot": snapshot(hourly) if not hourly.empty else None,
        "events": [e | {"days": (dt.date.fromisoformat(e["date"]) - today).days} for e in events
                   if (dt.date.fromisoformat(e["date"]) - today).days >= -7],
        "next_big_event": next_big | {"days": days_to_big} if next_big else None,
        "context": ctx,
        "backtest": backtest.all_tests(daily, hourly, cfg["signal_min_score"]),
        "track_record": track, "signal_min_score": cfg["signal_min_score"],
        "daily": bars(daily, False), "hourly": bars(hourly.tail(7 * 30), True) if not hourly.empty else [],
        "iv_history": iv_hist[-252:],
        "signal_grades": backtest.grade_all(daily, hourly),
        "news": news[:8],
        "launches": [x | {"notable": notable_launch(x)} for x in launches[:12]],
        "compare": compare_series(daily, data["context"]),
        "vol_history": [{"t": ts.strftime("%Y-%m-%d"), "rv": _num(v * 100, 1)} for ts, v in daily["rvol20"].items() if pd.notna(v)],
        "chain": opt.compact_chain(chain, spot), "rate": opt.RATE, "today": today.isoformat(),
    }
    moves = eventmoves.history(daily, events, em_hist, today)
    result["event_moves"] = {"rows": moves, "summary": eventmoves.summarize(moves)}
    recent = [e | {"days": (dt.date.fromisoformat(e["date"]) - today).days} for e in events
              if e["type"] in ("earnings", "lockup") and -2 <= (dt.date.fromisoformat(e["date"]) - today).days <= 0]
    result["today_paragraph"] = summary.paragraph(result, mode, today, recent[-1] if recent else None)
    weeks = weekly.build(daily, events, log, iv_hist, today)

    (OUT / "latest.json").write_text(json.dumps(result, separators=(",", ":")))
    (OUT / "weekly.json").write_text(json.dumps({"generated": result["generated"], "source": data["source"],
                                                  "weeks": weeks}, separators=(",", ":")))
    if not a.sample:
        (OUT / "signals.json").write_text(json.dumps(log, indent=1))
        (OUT / "state.json").write_text(json.dumps(state, indent=1))
        (OUT / "iv_history.json").write_text(json.dumps(iv_hist))
        (OUT / "expected_moves.json").write_text(json.dumps(em_hist, indent=1))
    print(f"{mode}: ${spot:.2f}  {label} ({score:+d})  options {vol['verdict']}  new strong signal: {new_signal}")


if __name__ == "__main__":
    main()
