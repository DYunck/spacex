"""Test how the direction score would have done on past SPCX price data.

Only the stock's direction is tested: free historical option prices aren't
available, so this says "was the call right?" not "would an option have paid?".
"""
from __future__ import annotations

import pandas as pd

from .signals import frame_score


def run(df: pd.DataFrame, horizons: list[int], threshold: float, label: str, weight: float = 1.0) -> list[dict]:
    scores = [frame_score(df, i, label, weight)[0] if i > 0 else 0 for i in range(len(df))]
    closes = df["Close"].values
    out = []
    for side, sign in (("Bullish", 1), ("Bearish", -1)):
        for h in horizons:
            rets = []
            for i, s in enumerate(scores):
                if i + h >= len(closes):
                    break
                if s * sign >= threshold * weight:
                    rets.append((closes[i + h] / closes[i] - 1) * sign * 100)
            n = len(rets)
            out.append({
                "timeframe": label, "signal": side, "horizon": f"{h} {'day' if label == 'Daily' else 'hour'}{'s' if h > 1 else ''}",
                "count": n,
                "win_rate": round(sum(r > 0 for r in rets) / n * 100) if n else None,
                "avg_move_pct": round(sum(rets) / n, 2) if n else None,
                "worst_pct": round(min(rets), 2) if n else None,
                "best_pct": round(max(rets), 2) if n else None,
            })
    return out


def all_tests(daily: pd.DataFrame, hourly: pd.DataFrame, threshold: float) -> dict:
    # Daily-only score tops out lower than the combined score, so test at a scaled threshold.
    t = threshold * 0.6
    rows = run(daily, [1, 5, 10], t, "Daily")
    if len(hourly) > 60:
        rows += run(hourly, [3, 7], t, "Hourly")
    return {
        "threshold": round(t),
        "rows": rows,
        "trading_days": len(daily),
        "note": ("SPCX has only traded since June 12, 2026, so these counts are small and the results "
                 "can change a lot as history builds. Treat them as a rough guide."),
    }


# ---------------------------------------------------------------- per-signal grading

# (key, plain-English name, direction it predicts, condition builder)
def _components(df: pd.DataFrame) -> list[tuple[str, str, int, pd.Series]]:
    c = df["Close"]
    prev_hist = df["macd_hist"].shift()
    move = c.diff()
    spike = df["Volume"] > 1.5 * df["vol_avg20"]
    return [
        ("above_sma20", "Price above 20-bar average", 1, c > df["sma20"]),
        ("below_sma20", "Price below 20-bar average", -1, c < df["sma20"]),
        ("uptrend", "20-bar average above 50-bar (uptrend)", 1, df["sma20"] > df["sma50"]),
        ("downtrend", "20-bar average below 50-bar (downtrend)", -1, df["sma20"] < df["sma50"]),
        ("rsi_oversold", "RSI under 30 (oversold)", 1, df["rsi"] < 30),
        ("rsi_overbought", "RSI over 70 (overbought)", -1, df["rsi"] > 70),
        ("macd_cross_up", "MACD crosses up", 1, (df["macd_hist"] > 0) & (prev_hist <= 0)),
        ("macd_cross_down", "MACD crosses down", -1, (df["macd_hist"] < 0) & (prev_hist >= 0)),
        ("bb_below", "Closed below lower Bollinger band", 1, c < df["bb_low"]),
        ("bb_above", "Closed above upper Bollinger band", -1, c > df["bb_up"]),
        ("vol_spike_up", "Up move on heavy volume", 1, spike & (move > 0)),
        ("vol_spike_down", "Down move on heavy volume", -1, spike & (move < 0)),
    ]


def grade(df: pd.DataFrame, label: str, horizon: int, min_count: int = 10) -> list[dict]:
    """For each individual signal: how often SPCX moved the predicted way `horizon` bars later."""
    if len(df) < horizon + 25:
        return []
    fwd = df["Close"].shift(-horizon) / df["Close"] - 1
    unit = "day" if label == "Daily" else "hour"
    out = []
    for key, name, sign, cond in _components(df):
        mask = cond.fillna(False) & fwd.notna()
        r = (fwd[mask] * sign * 100)
        n = int(mask.sum())
        win = round(float((r > 0).mean() * 100)) if n else None
        avg = round(float(r.mean()), 2) if n else None
        if n < min_count:
            verdict = "Too few"
        elif win >= 58 and avg > 0:
            verdict = "Helpful"
        elif win <= 42 or (win < 50 and avg < 0):
            verdict = "Misleading"
        else:
            verdict = "No edge"
        out.append({"key": key, "signal": name, "timeframe": label, "predicts": "up" if sign > 0 else "down",
                    "horizon": f"{horizon} {unit}{'s' if horizon > 1 else ''}", "count": n,
                    "win_rate": win, "avg_move_pct": avg, "verdict": verdict})
    order = {"Helpful": 0, "Misleading": 1, "No edge": 2, "Too few": 3}
    return sorted(out, key=lambda x: (order[x["verdict"]], -(x["win_rate"] or 0)))


def grade_all(daily: pd.DataFrame, hourly: pd.DataFrame) -> dict:
    rows = grade(daily, "Daily", 5)
    if len(hourly) > 60:
        rows += grade(hourly, "Hourly", 7)
    order = {"Helpful": 0, "Misleading": 1, "No edge": 2, "Too few": 3}
    rows.sort(key=lambda x: (order[x["verdict"]], -(x["count"] or 0)))
    return {"rows": rows,
            "note": ("Each signal is tested on its own: when it appeared, did SPCX move the way it predicts "
                     "5 trading days later (daily) or 7 hours later (hourly)? \"Helpful\" means right at least 58% of "
                     "the time with a positive average move, \"Misleading\" means wrong more often than right, and "
                     "\"Too few\" means under 10 examples so far.")}
