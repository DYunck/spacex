"""Main job: fetch data, analyze, write dashboard data, send alerts.

    python -m app.run              # live data, decides intraday vs. after-close summary by the clock
    python -m app.run --sample     # fake data for testing, sends nothing
    python -m app.run --mode summary --no-alerts
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
from pathlib import Path

import pandas as pd
import yaml

from . import alerts, backtest, fetch, indicators as ind, options as opt, signals

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


def load_positions() -> list[dict]:
    raw = yaml.safe_load((ROOT / "data" / "positions.yaml").read_text()) or {}
    return raw.get("positions") or []


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
    ap.add_argument("--no-alerts", action="store_true")
    a = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
    now = pd.Timestamp.now(tz=NY)
    today = now.date()
    OUT.mkdir(parents=True, exist_ok=True)
    send_alerts = not (a.no_alerts or a.sample)

    mode = a.mode
    if mode == "auto":
        mins = now.hour * 60 + now.minute
        mode = "summary" if mins >= 16 * 60 + 10 or mins < 9 * 60 + 30 else "intraday"

    data = fetch.fetch_sample(cfg) if a.sample else fetch.fetch_live(cfg)
    daily, hourly = data["daily"], data["hourly"]
    if daily.empty:
        raise SystemExit("No daily data returned — check the ticker in config.yaml")

    daily = ind.add_all(daily, 252)
    hourly = ind.add_all(hourly, 252 * 6.5) if not hourly.empty else hourly
    spot = float(hourly["Close"].iloc[-1]) if not hourly.empty and hourly.index[-1] > daily.index[-1] else float(daily["Close"].iloc[-1])
    prev_close = float(daily["Close"].iloc[-2]) if len(daily) > 1 else spot
    if not hourly.empty and hourly.index[-1].date() == daily.index[-1].date() and len(daily) > 1:
        prev_close = float(daily["Close"].iloc[-2])

    events = load_events(today)
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

    # ---- signals
    direction = signals.direction(daily, hourly)
    vol = signals.volatility_verdict(iv, rv, iv_rank, days_to_big)
    stance = signals.stance(direction["score"], vol["verdict"])
    calls = opt.suggest(chain, "call", cfg, events, today)
    puts = opt.suggest(chain, "put", cfg, events, today)

    # ---- positions
    pos_out, pos_alerts = [], []
    rules = cfg["exit_rules"]
    for p in load_positions():
        try:
            exp = str(p["expiry"])
            k, typ = float(p["strike"]), str(p["type"]).lower()
            m = chain[(chain["expiry"] == exp) & (chain["strike"] == k) & (chain["type"] == typ)] if not chain.empty else chain
            dte = (dt.date.fromisoformat(exp) - today).days
            item = {"contract": f"SPCX {exp} ${k:g} {typ}", "contracts": int(p.get("contracts", 1)),
                    "cost_per_contract": float(p["cost_per_contract"]), "dte": dte}
            if m is not None and not m.empty:
                r = m.iloc[0]
                val = r["mid"] * 100
                pl = (val / item["cost_per_contract"] - 1) * 100
                item |= {"value_per_contract": round(val, 0), "pl_pct": round(pl, 1),
                         "pl_dollars": round((val - item["cost_per_contract"]) * item["contracts"], 0),
                         "delta": _num(r["delta"]), "theta_per_day": _num(r["theta"] * 100)}
                if pl >= rules["take_profit_pct"]:
                    pos_alerts.append((item["contract"], "profit", f"{item['contract']} is up {pl:.0f}% — consider taking profit"))
                if pl <= rules["stop_loss_pct"]:
                    pos_alerts.append((item["contract"], "loss", f"{item['contract']} is down {pl:.0f}% — your stop-loss level"))
                against = (typ == "call" and direction["score"] <= -40) or (typ == "put" and direction["score"] >= 40)
                if against:
                    pos_alerts.append((item["contract"], "against", f"Signals have turned against {item['contract']} ({direction['label']})"))
            else:
                item["note"] = "Contract not found in downloaded chain"
            if dte <= rules["min_days_left"]:
                pos_alerts.append((item["contract"], "decay", f"{item['contract']} has {dte} days left — time decay speeds up from here"))
            if next_big and dt.date.fromisoformat(next_big["date"]) <= dt.date.fromisoformat(exp) and days_to_big is not None and days_to_big <= 3:
                pos_alerts.append((item["contract"], "event", f"{item['contract']} will be held through: {next_big['title']}"))
            pos_out.append(item)
        except Exception as e:
            pos_out.append({"contract": str(p), "note": f"Couldn't read this position: {e}"})

    # ---- alert log + outcomes
    state = _load_json(OUT / "state.json", {})
    log = _load_json(OUT / "alerts.json", [])
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

    fired = []
    score, label = direction["score"], direction["label"]
    strong = abs(score) >= cfg["alert_min_score"]
    if mode == "intraday" and strong and state.get("last_signal_label") != label:
        title = f"SPCX {label} signal ({score:+d}) — ${spot:.2f}"
        reasons = "\n".join(f"• {r['text']}" for r in direction["reasons"][:6])
        vn = "\n".join(f"• {n}" for n in vol["notes"])
        top = (calls if score > 0 else puts)[:1]
        sug = f"\nContract to look at: {top[0]['contract']} ~${top[0]['cost']:.0f}, breakeven ${top[0]['breakeven']}" if top else ""
        body = f"{stance['action']}\n{stance['detail']}\n\nWhy:\n{reasons}\n\nOption prices: {vol['verdict']}\n{vn}{sug}\n\nNot financial advice — you decide."
        fired.append({"kind": "signal", "title": title, "body": body, "direction": "up" if score > 0 else "down"})
        state["last_signal_label"] = label
    if not strong and abs(score) < cfg["alert_min_score"] * 0.5:
        state["last_signal_label"] = None  # re-arm once things calm down

    sent_pos = state.setdefault("position_alerts", {})
    for contract, kind, text in pos_alerts:
        key = f"{contract}|{kind}"
        if sent_pos.get(key) != today.isoformat() and (kind in ("decay", "event") or key not in sent_pos):
            fired.append({"kind": "position", "title": f"SPCX position: {text}", "body": text + "\n\nNot financial advice — you decide."})
            sent_pos[key] = today.isoformat()

    if mode == "summary" and state.get("last_summary") != today.isoformat():
        chg = (spot / prev_close - 1) * 100
        nxt = f"Next big event: {next_big['title']} in {days_to_big} day(s)" if next_big else ""
        body = (f"Close ${spot:.2f} ({chg:+.1f}%)\nSignal: {label} ({score:+d})\n{stance['action']}\n"
                f"Option prices: {vol['verdict']}" + (f", IV {iv*100:.0f}%" if iv else "") +
                (f", IV/actual {vol['iv_rv_ratio']}" if vol['iv_rv_ratio'] else "") + f"\n{nxt}")
        fired.append({"kind": "summary", "title": f"SPCX daily summary — {label}", "body": body + "\n\nNot financial advice."})
        state["last_summary"] = today.isoformat()

    for f in fired:
        channels = alerts.send(f["title"], f["body"]) if send_alerts else []
        if f["kind"] != "summary":
            log.append({"time": now.isoformat(timespec="minutes"), "kind": f["kind"], "title": f["title"],
                        "label": label, "score": score, "price": round(spot, 2),
                        "direction": f.get("direction"), "sent_via": channels})
    log = log[-300:]

    # ---- signal track record from the alert log
    graded = [e for e in log if e.get("right_5d") is not None]
    track = {"alerts": len([e for e in log if e["kind"] == "signal"]), "graded_5d": len(graded),
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
        "positions": pos_out, "context": ctx,
        "backtest": backtest.all_tests(daily, hourly, cfg["alert_min_score"]),
        "track_record": track, "alert_min_score": cfg["alert_min_score"],
        "daily": bars(daily, False), "hourly": bars(hourly.tail(7 * 30), True) if not hourly.empty else [],
        "iv_history": iv_hist[-252:],
    }

    (OUT / "latest.json").write_text(json.dumps(result, separators=(",", ":")))
    if not a.sample:
        (OUT / "alerts.json").write_text(json.dumps(log, indent=1))
        (OUT / "state.json").write_text(json.dumps(state, indent=1))
        (OUT / "iv_history.json").write_text(json.dumps(iv_hist))
    print(f"{mode}: ${spot:.2f}  {label} ({score:+d})  options {vol['verdict']}  alerts fired: {len(fired)}")


if __name__ == "__main__":
    main()
