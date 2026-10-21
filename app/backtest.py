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
