"""Turn indicators into a direction score, a volatility verdict and a plain-English stance."""
from __future__ import annotations

import math

import pandas as pd


def _ok(x) -> bool:
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def frame_score(df: pd.DataFrame, i: int, label: str, weight: float = 1.0) -> tuple[float, list[dict]]:
    """Score one bar (row i) of a timeframe. Positive = bullish, negative = bearish."""
    r = df.iloc[i]
    prev = df.iloc[i - 1] if i > 0 else r
    pts: list[tuple[float, str]] = []
    c = r["Close"]

    if _ok(r["sma20"]):
        pts.append((10, f"{label}: price above its 20-bar average") if c > r["sma20"]
                   else (-10, f"{label}: price below its 20-bar average"))
    if _ok(r["sma20"]) and _ok(r["sma50"]):
        pts.append((8, f"{label}: 20-bar average above 50-bar (uptrend)") if r["sma20"] > r["sma50"]
                   else (-8, f"{label}: 20-bar average below 50-bar (downtrend)"))
    if _ok(r["rsi"]):
        if r["rsi"] < 30:
            pts.append((12, f"{label}: RSI {r['rsi']:.0f} — oversold, bounce more likely"))
        elif r["rsi"] > 70:
            pts.append((-12, f"{label}: RSI {r['rsi']:.0f} — overbought, pullback more likely"))
        elif r["rsi"] > 55:
            pts.append((4, f"{label}: RSI {r['rsi']:.0f} — positive momentum"))
        elif r["rsi"] < 45:
            pts.append((-4, f"{label}: RSI {r['rsi']:.0f} — weak momentum"))
    if _ok(r["macd_hist"]) and _ok(prev["macd_hist"]):
        if r["macd_hist"] > 0 and prev["macd_hist"] <= 0:
            pts.append((12, f"{label}: MACD just crossed up (bullish)"))
        elif r["macd_hist"] < 0 and prev["macd_hist"] >= 0:
            pts.append((-12, f"{label}: MACD just crossed down (bearish)"))
        elif r["macd_hist"] > 0:
            pts.append((5, f"{label}: MACD positive"))
        else:
            pts.append((-5, f"{label}: MACD negative"))
    if _ok(r["bb_low"]) and c < r["bb_low"]:
        pts.append((8, f"{label}: closed below lower Bollinger band (stretched down)"))
    if _ok(r["bb_up"]) and c > r["bb_up"]:
        pts.append((-8, f"{label}: closed above upper Bollinger band (stretched up)"))
    if _ok(r["vol_avg20"]) and r["vol_avg20"] > 0 and r["Volume"] > 1.5 * r["vol_avg20"]:
        move = c - prev["Close"]
        if move != 0:
            pts.append((8 if move > 0 else -8,
                        f"{label}: {'up' if move > 0 else 'down'} move on {r['Volume'] / r['vol_avg20']:.1f}x normal volume"))

    score = sum(p for p, _ in pts) * weight
    return score, [{"points": round(p * weight, 1), "text": t} for p, t in pts]


def trend_dir(df: pd.DataFrame) -> int:
    r = df.iloc[-1]
    if not _ok(r["sma20"]):
        return 0
    return 1 if r["Close"] > r["sma20"] else -1


def direction(daily: pd.DataFrame, hourly: pd.DataFrame) -> dict:
    ds, dr = frame_score(daily, len(daily) - 1, "Daily", 1.0)
    reasons = list(dr)
    hs = 0.0
    if len(hourly) > 2:
        hs, hr = frame_score(hourly, len(hourly) - 1, "Hourly", 0.6)
        reasons += hr
    agree = trend_dir(daily) * trend_dir(hourly) if len(hourly) > 2 else 0
    bonus = 0
    if agree == 1:
        bonus = 10 * trend_dir(daily)
        reasons.append({"points": bonus, "text": "Daily and hourly trends agree"})
    elif agree == -1:
        reasons.append({"points": 0, "text": "Daily and hourly trends disagree — lower confidence"})
    score = max(-100, min(100, ds + hs + bonus))
    reasons.sort(key=lambda x: -abs(x["points"]))
    return {"score": round(score), "daily_score": round(ds), "hourly_score": round(hs), "reasons": reasons,
            "label": label_for(score)}


def label_for(score: float) -> str:
    if score >= 40:
        return "Bullish"
    if score >= 20:
        return "Leaning bullish"
    if score <= -40:
        return "Bearish"
    if score <= -20:
        return "Leaning bearish"
    return "Neutral"


def volatility_verdict(iv: float | None, rv: float | None, iv_rank: float | None, days_to_event: int | None) -> dict:
    notes = []
    verdict = "fair"
    ratio = iv / rv if iv and rv else None
    if iv_rank is not None:
        if iv_rank >= 70:
            verdict = "expensive"
            notes.append(f"IV rank {iv_rank:.0f}: options are near the priciest they've been")
        elif iv_rank <= 30:
            verdict = "cheap"
            notes.append(f"IV rank {iv_rank:.0f}: options are near the cheapest they've been")
    if ratio:
        if ratio >= 1.3:
            verdict = "expensive"
            notes.append(f"Options price in {ratio:.1f}x the swings the stock is actually making")
        elif ratio <= 0.9 and verdict != "expensive":
            verdict = "cheap"
            notes.append(f"Options price in less movement ({ratio:.1f}x) than the stock is actually making")
    if days_to_event is not None and 0 <= days_to_event <= 7:
        notes.append(f"Major event in {days_to_event} day(s): option prices usually drop sharply right after it (volatility crush)")
    return {"verdict": verdict, "iv_rv_ratio": round(ratio, 2) if ratio else None, "notes": notes}


def stance(dir_score: float, vol: str) -> dict:
    """Plain-English summary of what conditions favor. Never an instruction to trade."""
    lab = label_for(dir_score)
    if lab == "Bullish":
        if vol == "expensive":
            return {"action": "Bullish, but options are pricey",
                    "detail": "Direction favors calls, but premiums are high. A call spread (buy one call, sell a higher one) "
                              "costs less, or wait for implied volatility to fall."}
        return {"action": "Conditions favor buying calls",
                "detail": "Trend and momentum point up and option prices are reasonable. Check the suggested contracts below."}
    if lab == "Bearish":
        if vol == "expensive":
            return {"action": "Bearish, but options are pricey",
                    "detail": "Direction favors puts, but premiums are high. A put spread costs less, or wait. "
                              "Good time to take profits on calls you own."}
        return {"action": "Conditions favor buying puts / selling calls you own",
                "detail": "Trend and momentum point down. If you hold calls, consider selling them; puts are a way to bet on a drop."}
    if lab == "Leaning bullish":
        return {"action": "Leaning bullish — wait for confirmation",
                "detail": "Some signals point up but not enough agree yet. Watch for the score to reach ±40 (a strong signal)."}
    if lab == "Leaning bearish":
        return {"action": "Leaning bearish — consider protecting gains",
                "detail": "Some signals point down. If you hold calls that are profitable, consider taking some profit."}
    if vol == "expensive":
        return {"action": "No clear direction; options expensive",
                "detail": "No edge on direction, and buying options now means overpaying. Usually a time to sell options you own, not buy."}
    return {"action": "No clear signal — wait",
            "detail": "Signals are mixed. Waiting is a valid choice; options lose value every day you hold them."}
