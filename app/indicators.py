"""Technical indicators, computed the same way on daily and hourly bars."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rs = up / dn.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def macd(s: pd.Series, fast=12, slow=26, sig=9):
    line = ema(s, fast) - ema(s, slow)
    signal = line.ewm(span=sig, adjust=False, min_periods=sig).mean()
    return line, signal, line - signal


def bollinger(s: pd.Series, n=20, k=2.0):
    mid = sma(s, n)
    sd = s.rolling(n, min_periods=n).std()
    return mid + k * sd, mid, mid - k * sd


def atr(df: pd.DataFrame, n=14) -> pd.Series:
    pc = df["Close"].shift()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def realized_vol(s: pd.Series, n: int, periods_per_year: float) -> pd.Series:
    r = np.log(s / s.shift())
    return r.rolling(n, min_periods=max(5, n // 2)).std() * math.sqrt(periods_per_year)


def add_all(df: pd.DataFrame, periods_per_year: float) -> pd.DataFrame:
    df = df.copy()
    c = df["Close"]
    df["sma20"] = sma(c, 20)
    df["sma50"] = sma(c, 50)
    df["rsi"] = rsi(c)
    df["macd"], df["macd_signal"], df["macd_hist"] = macd(c)
    df["bb_up"], df["bb_mid"], df["bb_low"] = bollinger(c)
    df["atr"] = atr(df)
    df["vol_avg20"] = df["Volume"].rolling(20, min_periods=5).mean()
    df["rvol20"] = realized_vol(c, 20, periods_per_year)
    return df


def support_resistance(daily: pd.DataFrame, ipo_price: float, window: int = 5, max_levels: int = 6) -> list[dict]:
    """Swing highs/lows clustered within 2%, plus the IPO price."""
    if len(daily) < window * 2 + 1:
        return [{"price": round(ipo_price, 2), "kind": "IPO price"}]
    hi, lo = daily["High"], daily["Low"]
    pts = []
    for i in range(window, len(daily) - window):
        if hi.iloc[i] == hi.iloc[i - window:i + window + 1].max():
            pts.append(hi.iloc[i])
        if lo.iloc[i] == lo.iloc[i - window:i + window + 1].min():
            pts.append(lo.iloc[i])
    pts.sort()
    clusters: list[list[float]] = []
    for p in pts:
        if clusters and abs(p / np.mean(clusters[-1]) - 1) < 0.02:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    last = daily["Close"].iloc[-1]
    levels = sorted(clusters, key=lambda c: (-len(c), abs(np.mean(c) - last)))[:max_levels]
    out = [{"price": round(float(np.mean(c)), 2), "kind": "support" if np.mean(c) < last else "resistance",
            "touches": len(c)} for c in levels]
    out.append({"price": round(ipo_price, 2), "kind": "IPO price", "touches": 0})
    return sorted(out, key=lambda x: x["price"])
