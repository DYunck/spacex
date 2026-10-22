"""Download SPCX price history and option chains (Yahoo Finance via yfinance).

Also provides a --sample mode that generates realistic fake data so the
dashboard can be tested without network access.
"""
from __future__ import annotations

import datetime as dt
import math

import numpy as np
import pandas as pd

NY = "America/New_York"


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["Open", "High", "Low", "Close", "Volume"])
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])
    if df.index.tz is None:
        df.index = df.index.tz_localize(NY)
    else:
        df.index = df.index.tz_convert(NY)
    return df


def fetch_live(cfg: dict) -> dict:
    import yfinance as yf

    sym = cfg["ticker"]
    t = yf.Ticker(sym)
    daily = _clean(t.history(start=cfg["ipo_date"], interval="1d", auto_adjust=False))
    hourly = _clean(t.history(period="60d", interval="60m", auto_adjust=False))

    context = {}
    for c in cfg.get("context_tickers", {}):
        try:
            context[c] = _clean(yf.Ticker(c).history(start=cfg["ipo_date"], interval="1d", auto_adjust=False))
        except Exception as e:  # context is nice-to-have
            print(f"context {c} failed: {e}")
            context[c] = _clean(None)

    chains = []
    try:
        expiries = list(t.options)[: cfg.get("option_expirations", 6)]
    except Exception as e:
        print(f"option expiries failed: {e}")
        expiries = []
    for exp in expiries:
        try:
            oc = t.option_chain(exp)
        except Exception as e:
            print(f"chain {exp} failed: {e}")
            continue
        for kind, frame in (("call", oc.calls), ("put", oc.puts)):
            f = frame.copy()
            f["type"] = kind
            f["expiry"] = exp
            chains.append(f)
    chain = pd.concat(chains, ignore_index=True) if chains else pd.DataFrame()
    return {"daily": daily, "hourly": hourly, "context": context, "chain": chain, "source": "Yahoo Finance",
            "news": fetch_news(t), "launches": fetch_launches(),
            "starship": fetch_starship_flights(), "analysts": fetch_analysts(t), "shares": fetch_share_info(t)}


# ---------------------------------------------------------------- news & launches

def _parse_news_items(raw) -> list[dict]:
    out = []
    for n in raw or []:
        c = n.get("content") if isinstance(n, dict) and isinstance(n.get("content"), dict) else n
        if not isinstance(c, dict):
            continue
        title = c.get("title")
        link = ((c.get("clickThroughUrl") or {}).get("url") or (c.get("canonicalUrl") or {}).get("url") or c.get("link"))
        pub = (c.get("provider") or {}).get("displayName") or c.get("publisher") or ""
        when = c.get("pubDate") or c.get("displayTime")
        if not when and c.get("providerPublishTime"):
            when = dt.datetime.fromtimestamp(c["providerPublishTime"], dt.timezone.utc).isoformat()
        if title and link and str(link).startswith("http"):
            out.append({"title": title, "url": link, "publisher": pub, "time": when})
    return out


def _news_rss(symbol: str) -> list[dict]:
    """Yahoo's per-ticker RSS headline feed (a different service from the yfinance news call)."""
    import email.utils
    import xml.etree.ElementTree as ET

    import requests
    r = requests.get("https://feeds.finance.yahoo.com/rss/2.0/headline",
                     params={"s": symbol, "region": "US", "lang": "en-US"}, timeout=20,
                     headers={"User-Agent": "Mozilla/5.0 (spcx-signals dashboard)"})
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        title, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
        when = it.findtext("pubDate")
        try:
            when = email.utils.parsedate_to_datetime(when).isoformat() if when else None
        except Exception:
            pass
        src = it.find("source")
        if title and link.startswith("http"):
            out.append({"title": title, "url": link, "publisher": (src.text if src is not None and src.text else "Yahoo Finance"), "time": when})
    return out


_RELEVANT = ("spacex", "spcx", "starship", "starlink", "falcon", "musk", "space x", "xai")


def _rank(items: list[dict]) -> list[dict]:
    """SpaceX-related headlines first; general market stories after."""
    rel = [x for x in items if any(k in x["title"].lower() for k in _RELEVANT)]
    return rel + [x for x in items if x not in rel]


def fetch_news(ticker, limit: int = 8) -> list[dict] | None:
    """Latest SPCX headlines. Tries several Yahoo sources; returns None only if all of them fail (keep the cache)."""
    got_any_response = False
    attempts = [
        ("news", lambda: ticker.get_news(count=limit + 6, tab="news")),
        ("all", lambda: ticker.get_news(count=limit + 6, tab="all")),
        ("press releases", lambda: ticker.get_news(count=limit + 6, tab="press releases")),
    ]
    for name, call in attempts:
        try:
            ticker._news = []  # yfinance caches the first answer; clear it between tabs
            items = _parse_news_items(call())
            got_any_response = True
            print(f"news ({name}): {len(items)} headlines")
            if items:
                return _rank(items)[:limit]
        except Exception as e:
            print(f"news ({name}) failed: {e}")
    try:
        items = _news_rss(ticker.ticker)
        got_any_response = True
        print(f"news (rss): {len(items)} headlines")
        if items:
            return _rank(items)[:limit]
    except Exception as e:
        print(f"news (rss) failed: {e}")
    return [] if got_any_response else None


def fetch_launches(limit: int = 12) -> list[dict] | None:
    """Upcoming SpaceX launches from The Space Devs Launch Library 2 (free, no key). None on failure."""
    import requests
    url = "https://ll.thespacedevs.com/2.3.0/launches/upcoming/"
    try:
        r = requests.get(url, params={"lsp__name": "SpaceX", "limit": limit, "mode": "normal"}, timeout=20,
                         headers={"User-Agent": "spcx-signals-dashboard"})
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as e:
        print(f"launches failed: {e}")
        return None
    out = []
    for x in results:
        rocket = ((x.get("rocket") or {}).get("configuration") or {})
        mission = x.get("mission") or {}
        pad = x.get("pad") or {}
        status = x.get("status") or {}
        out.append({
            "name": x.get("name") or "",
            "net": x.get("net"),
            "status": status.get("abbrev") or status.get("name") or "",
            "status_name": status.get("name") or "",
            "rocket": rocket.get("name") or rocket.get("full_name") or "",
            "mission": mission.get("name") or "",
            "mission_type": mission.get("type") or "",
            "orbit": ((mission.get("orbit") or {}).get("abbrev")) or "",
            "pad": pad.get("name") or "",
            "location": ((pad.get("location") or {}).get("name")) or "",
        })
    return out


def fetch_starship_flights(since: str = "2025-01-01") -> list[dict] | None:
    """Past Starship flights from The Space Devs Launch Library 2. None on failure (keep the cache)."""
    import requests
    url = "https://ll.thespacedevs.com/2.3.0/launches/previous/"
    try:
        r = requests.get(url, params={"search": "Starship", "net__gte": since, "limit": 40, "mode": "detailed",
                                      "ordering": "-net"}, timeout=25, headers={"User-Agent": "spcx-signals-dashboard"})
        r.raise_for_status()
        results = r.json().get("results", [])
    except Exception as e:
        print(f"starship flights failed: {e}")
        return None
    out = []
    for x in results:
        rocket = ((x.get("rocket") or {}).get("configuration") or {})
        name = x.get("name") or ""
        if "starship" not in (name + " " + (rocket.get("name") or "")).lower():
            continue
        status = x.get("status") or {}
        mission = x.get("mission") or {}
        out.append({
            "name": name, "net": x.get("net"),
            "status": status.get("abbrev") or status.get("name") or "",
            "status_name": status.get("name") or "",
            "failreason": (x.get("failreason") or "").strip(),
            "mission": mission.get("name") or "",
            "description": (mission.get("description") or "").strip(),
        })
    print(f"starship flights: {len(out)}")
    return out


def _num_or_none(x):
    try:
        f = float(x)
        return None if f != f else f
    except (TypeError, ValueError):
        return None


def fetch_analysts(ticker) -> dict | None:
    """Wall Street price targets, rating mix and recent rating changes (Yahoo). None if nothing came back."""
    out = {}
    try:
        pt = ticker.get_analyst_price_targets() or {}
        out["targets"] = {k: _num_or_none(pt.get(k)) for k in ("low", "mean", "median", "high", "current")}
    except Exception as e:
        print(f"analyst targets failed: {e}")
    try:
        info = ticker.info or {}
        out["count"] = info.get("numberOfAnalystOpinions")
        out["rating_key"] = info.get("recommendationKey")
        out["rating_mean"] = _num_or_none(info.get("recommendationMean"))
        t = out.setdefault("targets", {})
        for k, ik in (("low", "targetLowPrice"), ("mean", "targetMeanPrice"), ("median", "targetMedianPrice"), ("high", "targetHighPrice")):
            if t.get(k) is None:
                t[k] = _num_or_none(info.get(ik))
    except Exception as e:
        print(f"analyst info failed: {e}")
    try:
        rec = ticker.get_recommendations_summary()
        if rec is not None and len(rec):
            row = rec.iloc[0]
            out["mix"] = {k: int(row.get(k, 0) or 0) for k in ("strongBuy", "buy", "hold", "sell", "strongSell")}
    except Exception as e:
        print(f"analyst mix failed: {e}")
    try:
        ud = ticker.get_upgrades_downgrades()
        if ud is not None and len(ud):
            ud = ud.reset_index().sort_values(ud.reset_index().columns[0], ascending=False).head(10)
            out["changes"] = [{
                "date": str(r.get("GradeDate", r.iloc[0]))[:10], "firm": r.get("Firm", ""),
                "to": r.get("ToGrade", ""), "from": r.get("FromGrade", ""), "action": r.get("Action", ""),
                "target": _num_or_none(r.get("currentPriceTarget")), "prior_target": _num_or_none(r.get("priorPriceTarget")),
            } for _, r in ud.iterrows()]
    except Exception as e:
        print(f"analyst changes failed: {e}")
    has = any(v is not None for v in (out.get("targets") or {}).values()) or out.get("mix") or out.get("changes")
    print(f"analysts: {'ok' if has else 'nothing returned'}")
    return out if has else None


def fetch_share_info(ticker) -> dict | None:
    try:
        info = ticker.info or {}
        return {"outstanding": info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"),
                "float": info.get("floatShares"), "insiders_pct": _num_or_none(info.get("heldPercentInsiders")),
                "institutions_pct": _num_or_none(info.get("heldPercentInstitutions"))}
    except Exception as e:
        print(f"share info failed: {e}")
        return None


# ---------------------------------------------------------------- sample data

def _sample_path(n: int, start: float, vol: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    rets = rng.normal(0, vol, n)
    # mimic the real shape: pop, long slide, recovery
    drift = np.concatenate([
        np.full(n // 6, 0.02), np.full(n // 3, -0.012), np.full(n - n // 6 - n // 3, 0.006)
    ])[:n]
    return start * np.exp(np.cumsum(rets + drift))


def fetch_sample(cfg: dict) -> dict:
    end = pd.Timestamp.now(tz=NY).normalize().tz_localize(None)
    days = pd.bdate_range(cfg["ipo_date"], end).tz_localize(NY)
    n = len(days)
    close = _sample_path(n, cfg["ipo_price"] * 1.15, 0.035, 1)
    rng = np.random.default_rng(2)
    openp = close * (1 + rng.normal(0, 0.01, n))
    high = np.maximum(openp, close) * (1 + abs(rng.normal(0, 0.015, n)))
    low = np.minimum(openp, close) * (1 - abs(rng.normal(0, 0.015, n)))
    vol = rng.integers(40e6, 120e6, n)
    daily = pd.DataFrame({"Open": openp, "High": high, "Low": low, "Close": close, "Volume": vol}, index=days)

    hrs = []
    for d in days[-40:]:
        for h in range(7):
            hrs.append(d + pd.Timedelta(hours=9, minutes=30) + pd.Timedelta(hours=h))
    hidx = pd.DatetimeIndex(hrs)
    hclose = _sample_path(len(hidx), close[-40], 0.012, 3)
    hclose *= close[-1] / hclose[-1]
    hopen = np.roll(hclose, 1); hopen[0] = hclose[0]
    hourly = pd.DataFrame({
        "Open": hopen, "High": np.maximum(hopen, hclose) * 1.004, "Low": np.minimum(hopen, hclose) * 0.996,
        "Close": hclose, "Volume": rng.integers(4e6, 18e6, len(hidx)),
    }, index=hidx)

    context = {}
    for i, c in enumerate(cfg.get("context_tickers", {})):
        base = {"QQQ": 610, "^VIX": 18, "TSLA": 420}.get(c, 100)
        cd = pd.bdate_range(cfg["ipo_date"], end).tz_localize(NY)
        cc = _sample_path(len(cd), base, 0.015, 10 + i)
        context[c] = pd.DataFrame({"Open": cc, "High": cc, "Low": cc, "Close": cc, "Volume": 0}, index=cd)

    spot = close[-1]
    rows = []
    today = end.date()
    exps = []
    d = today
    while len(exps) < cfg.get("option_expirations", 6):
        d += dt.timedelta(days=1)
        if d.weekday() == 4:
            exps.append(d)
    exps = exps[:2] + [x for x in _third_fridays(today, 6) if x > exps[1]][:4]
    from .options import bs_price
    for e in exps:
        T = max((e - today).days, 1) / 365
        for k in np.arange(round(spot * 0.6 / 5) * 5, spot * 1.4, 5):
            for kind in ("call", "put"):
                iv = 0.62 + 0.25 * abs(math.log(k / spot)) + (0.08 if (e - today).days < 10 else 0)
                p = bs_price(spot, k, T, iv, kind)
                spr = max(0.05, p * 0.04)
                oi = int(max(0, 8000 * math.exp(-abs(k - spot) / (spot * 0.12)) * rng.uniform(0.5, 1.5)))
                rows.append({
                    "contractSymbol": f"SPCX{e:%y%m%d}{kind[0].upper()}{int(k*1000):08d}",
                    "strike": float(k), "lastPrice": p, "bid": max(0, p - spr / 2), "ask": p + spr / 2,
                    "volume": int(oi * rng.uniform(0.05, 0.6)), "openInterest": oi,
                    "impliedVolatility": iv, "type": kind, "expiry": e.isoformat(),
                })
    now = pd.Timestamp.now(tz="UTC")
    news = [{"title": f"Sample headline {i + 1} about SpaceX stock (test data)", "url": "https://example.com/",
             "publisher": ["Reuters", "Bloomberg", "Yahoo Finance"][i % 3], "time": (now - pd.Timedelta(hours=5 * i + 1)).isoformat()}
            for i in range(6)]
    launches = [{"name": n, "net": (now + pd.Timedelta(days=d)).isoformat(), "status": st, "status_name": st,
                 "rocket": r, "mission": n.split(" | ")[-1], "mission_type": mt, "orbit": "LEO", "pad": "SLC-40",
                 "location": loc}
                for n, d, st, r, mt, loc in [
                    ("Falcon 9 Block 5 | Starlink Group 12-3", 1, "Go", "Falcon 9", "Communications", "Cape Canaveral, FL, USA"),
                    ("Starship | Flight 12", 6, "TBC", "Starship", "Test Flight", "Starbase, TX, USA"),
                    ("Falcon 9 Block 5 | Transporter-15", 9, "TBD", "Falcon 9", "Dedicated Rideshare", "Vandenberg SFB, CA, USA"),
                    ("Falcon Heavy | Sample Mission", 18, "TBD", "Falcon Heavy", "Government/Top Secret", "Kennedy Space Center, FL, USA")]]
    return {"daily": daily, "hourly": hourly, "context": context, "chain": pd.DataFrame(rows), "source": "SAMPLE DATA (not real)",
            "news": news, "launches": launches,
            "starship": _sample_starship(end), "analysts": _sample_analysts(close[-1]),
            "shares": {"outstanding": 13_200_000_000, "float": 2_900_000_000, "insiders_pct": 0.62, "institutions_pct": 0.21}}


def _sample_starship(end) -> list[dict]:
    rows = [(-98, "Starship | Flight 12", "Success", ""), (-92, "Starship | Flight 12 (scrubbed attempt)", "Failure", "Engines failed to start; launch aborted"),
            (-60, "Starship | Flight 13", "Partial Failure", "Booster lost on return"), (-25, "Starship | Flight 14", "Success", ""),
            (-200, "Starship | Flight 11", "Success", "")]
    def ts(d):
        t = pd.Timestamp(end) + pd.Timedelta(days=d, hours=18, minutes=30)
        return (t.tz_localize(NY) if t.tzinfo is None else t).tz_convert("UTC").isoformat()
    return [{"name": n, "net": ts(d), "status": st,
             "status_name": st, "failreason": fr, "mission": n.split("| ")[-1], "description": "Sample test flight (not real data)."}
            for d, n, st, fr in rows]


def _sample_analysts(price: float) -> dict:
    return {"targets": {"low": round(price * 0.6), "mean": round(price * 1.12), "median": round(price * 1.1),
                        "high": round(price * 1.7), "current": round(price, 2)},
            "count": 18, "rating_key": "buy", "rating_mean": 2.1,
            "mix": {"strongBuy": 5, "buy": 7, "hold": 5, "sell": 1, "strongSell": 0},
            "changes": [{"date": "2026-10-21", "firm": "Sample Securities", "to": "Buy", "from": "Hold", "action": "up",
                         "target": round(price * 1.25), "prior_target": round(price * 1.05)},
                        {"date": "2026-10-15", "firm": "Example Capital", "to": "Hold", "from": "Hold", "action": "main",
                         "target": round(price * 1.0), "prior_target": round(price * 1.1)}]}


def _third_fridays(start: dt.date, count: int) -> list[dt.date]:
    out = []
    y, m = start.year, start.month
    while len(out) < count:
        first = dt.date(y, m, 1)
        fri = first + dt.timedelta(days=(4 - first.weekday()) % 7 + 14)
        if fri >= start:
            out.append(fri)
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out
