# SpaceX (SPCX) Options Signals

A dashboard and alert system that watches SpaceX stock (Nasdaq: **SPCX**) and its options. It tells you when conditions favor **buying or selling options**, and explains why.

**Open the dashboard:** https://dyunck.github.io/spacex/
**New here? Read the tutorial:** https://dyunck.github.io/spacex/guide.html

> This tool never places trades. It only analyzes and sends alerts. You make every decision and place every trade yourself at your broker. It is not financial advice. Signals can be wrong, and options can lose 100% of what you pay.

---

## What it does

Every hour during market hours (Mon–Fri), GitHub runs the analysis automatically:

1. **Downloads data:** SPCX daily prices since the IPO, hourly prices for the last 60 days, and option chains for the nearest 6 expirations. It also pulls the Nasdaq-100 (QQQ), the VIX and Tesla for market context.
2. **Calculates indicators on both daily and hourly charts:** moving averages (20 and 50), RSI, MACD, Bollinger bands, average true range, volume compared with normal, and actual volatility.
3. **Scores direction from −100 (bearish) to +100 (bullish).** The score gets a bonus when the daily and hourly trends agree.
4. **Checks whether options are cheap or expensive.** It compares implied volatility (what options assume) with the stock's actual movement, and tracks IV rank over time.
5. **Watches upcoming events:** earnings, lockup expirations, Fed meetings and monthly options expirations. It warns about *volatility crush*, the sharp drop in option prices that often follows earnings.
6. **Suggests contracts to look at.** Only liquid contracts make the list (tight bid/ask, real open interest). Each one shows its breakeven, max loss and daily time decay.
7. **Watches your positions,** if you list them, and alerts you when it may be time to **sell**: profit target hit, stop-loss hit, signals turned against you, under 21 days left, or an earnings date ahead.
8. **Sends alerts** to your phone and/or email, plus a daily summary after the close.
9. **Keeps score.** Every alert is logged along with how the stock moved 1, 5 and 10 days later, so you can see how reliable the signals have been. A backtest runs on SPCX's price history too.

## Get alerts on your phone (free, 2 minutes)

1. Install the **ntfy** app ([iPhone](https://apps.apple.com/app/ntfy/id1625396347) / [Android](https://play.google.com/store/apps/details?id=io.heckel.ntfy)).
2. In the app, tap **+** and subscribe to a topic with a hard-to-guess name, for example `spcx-alerts-k7q2m9`. Anyone who knows the name can read it, so make it random.
3. On GitHub, go to **Settings → Secrets and variables → Actions → New repository secret**. Set **Name** to `NTFY_TOPIC` and **Secret** to the same topic name.

That's it. The next hourly run will send alerts when a strong signal appears.

**Email (optional):** add these secrets as well: `SMTP_HOST` (e.g. `smtp.gmail.com`), `SMTP_PORT` (`587`), `SMTP_USER` (your Gmail address), `SMTP_PASS` (a [Gmail app password](https://myaccount.google.com/apppasswords), not your normal password) and `ALERT_EMAIL_TO`.

## Customize it (all editable right on GitHub)

| File | What to change |
|---|---|
| `data/positions.yaml` | Options you own, so you get **sell** alerts |
| `data/events.yaml` | Earnings dates, lockups, Starship launches and other events |
| `config.yaml` | Alert sensitivity (`alert_min_score`), profit target, stop-loss, which contracts get suggested |

Click the file, then the pencil icon, edit, and **Commit changes**. The dashboard updates within a few minutes.

To refresh right away, go to **Actions → Update SPCX signals → Run workflow**.

## Good to know

- **Short history.** SPCX has only traded since June 12, 2026, so the backtest has few examples. IV rank needs 20 trading days of collected data before it appears; until then the app compares implied volatility with actual volatility instead.
- **Data source.** Prices come from Yahoo Finance and may be delayed about 15 minutes. Option Greeks (delta, decay) are calculated by the app.
- **Timing.** GitHub's scheduled runs can be a few minutes late at busy times.
- **Public repo.** The dashboard can be seen by anyone with the link. Don't put account numbers or anything private in these files.

## How the pieces fit

```
app/fetch.py        download prices and option chains
app/indicators.py   RSI, MACD, moving averages, Bollinger bands, volatility
app/options.py      Greeks, expected move, put/call ratio, contract picks
app/signals.py      direction score + "options cheap or expensive" + plain-English stance
app/backtest.py     how the score did on past data
app/alerts.py       phone push (ntfy) and email
app/run.py          runs everything, writes docs/data/latest.json
docs/               the dashboard (GitHub Pages)
.github/workflows/  the hourly schedule
```

Run locally: `pip install -r requirements.txt`, then `python -m app.run --no-alerts`. Use `--sample` for fake data without internet access.
