# SpaceX (SPCX) Options Signals

A dashboard that watches SpaceX stock (Nasdaq: **SPCX**) and its options. It tells you when conditions favor **buying or selling options**, and explains why.

**Open the dashboard:** https://dyunck.github.io/spacex/
**New here? Read the tutorial:** https://dyunck.github.io/spacex/guide.html

> This tool never places trades and never sends messages. It only analyzes and shows results on the dashboard. You make every decision and place every trade yourself at your broker. It is not financial advice. Signals can be wrong, and options can lose 100% of what you pay.

---

## What it does

Every hour during market hours (Mon–Fri), GitHub runs the analysis automatically and updates the dashboard:

1. **Downloads data:** SPCX daily prices since the IPO, hourly prices for the last 60 days, and option chains for the nearest 6 expirations. It also pulls the Nasdaq-100 (QQQ), the VIX and Tesla for market context.
2. **Calculates indicators on both daily and hourly charts:** moving averages (20 and 50), RSI, MACD, Bollinger bands, average true range, volume compared with normal, and actual volatility.
3. **Scores direction from −100 (bearish) to +100 (bullish).** The score gets a bonus when the daily and hourly trends agree.
4. **Checks whether options are cheap or expensive.** It compares implied volatility (what options assume) with the stock's actual movement, and tracks IV rank over time.
5. **Watches upcoming events:** earnings, lockup expirations, Fed meetings and monthly options expirations. It warns about *volatility crush*, the sharp drop in option prices that often follows earnings.
6. **Suggests contracts to look at.** Only liquid contracts make the list (tight bid/ask, real open interest). Each one shows its breakeven, max loss and daily time decay.
7. **Writes a one-paragraph summary** of the day in plain English at the top of the dashboard.
8. **Has a "what if" payoff calculator.** Pick any contract (or a spread) and see estimated profit or loss at different prices and dates, including the effect of time decay and volatility crush.
9. **Shows how SPCX moved around past earnings and lockups,** and from now on records how big a move options priced in beforehand.
10. **Grades each signal** on SPCX's history (Helpful, No edge, Misleading or Too few) so you know which reasons in the score to trust.
11. **Explains itself.** Tap any ⓘ for a plain-English definition of that number or section.
12. **Option chain heat map** of volume or open interest across every strike and expiration.
13. **Launches, headlines and comparison:** upcoming SpaceX launches (Starship and other big missions added to events), the latest SPCX headlines, and a chart of SPCX vs. Tesla vs. the Nasdaq-100.
14. **Option prices over time:** implied vs. actual volatility, with earnings and lockups marked.
15. **Starship flight tracker:** each test flight's result and how SPCX moved afterward.
16. **Insider selling tracker:** the lockup unlock schedule, how much of the company is tradable now vs. later, and how SPCX moved on past unlock days (schedule in `data/lockups.yaml`).
17. **Analyst price targets:** low/average/high targets vs. today's price, consensus rating and recent rating changes.
18. **Weekly recap page** (`weekly.html`) with one summary card per week.
19. **Keeps score.** Every strong signal (score past ±40) is logged along with how the stock moved 1, 5 and 10 days later, so you can see how reliable the signals have been. A backtest runs on SPCX's price history too.

## Put it on your phone's Home Screen

On iPhone, open the dashboard in Safari, tap **Share**, then **Add to Home Screen**. On Android, use Chrome's menu and choose **Install app**. It opens full-screen like a regular app.

## Customize it (all editable right on GitHub)

| File | What to change |
|---|---|
| `data/events.yaml` | Earnings dates, lockups, Starship launches and other events |
| `data/lockups.yaml` | The share unlock schedule used by the insider selling tracker |
| `config.yaml` | What counts as a strong signal (`signal_min_score`) and which contracts get suggested |

Click the file, then the pencil icon, edit, and **Commit changes**. The dashboard updates within a few minutes.

To refresh right away, go to **Actions → Update SPCX signals → Run workflow**.

## Good to know

- **Short history.** SPCX has only traded since June 12, 2026, so the backtest has few examples. IV rank needs 20 trading days of collected data before it appears; until then the app compares implied volatility with actual volatility instead.
- **Data sources.** Prices and headlines come from Yahoo Finance and may be delayed about 15 minutes. Launch schedules come from The Space Devs Launch Library (free, rate-limited; the last good copy is kept if a fetch fails). Option Greeks (delta, decay) are calculated by the app.
- **Timing.** GitHub's scheduled runs can be a few minutes late at busy times.
- **Public repo.** The dashboard can be seen by anyone with the link. Don't put account numbers or anything private in these files.

## How the pieces fit

```
app/fetch.py        download prices and option chains
app/indicators.py   RSI, MACD, moving averages, Bollinger bands, volatility
app/options.py      Greeks, expected move, put/call ratio, contract picks
app/signals.py      direction score + "options cheap or expensive" + plain-English stance
app/backtest.py     how the score did on past data, and per-signal grading
app/eventmoves.py   moves around past earnings and lockups
app/summary.py      the plain-English daily paragraph
app/weekly.py       weekly recap data (docs/data/weekly.json)
app/run.py          runs everything, writes docs/data/latest.json
docs/               the dashboard (GitHub Pages): calculator (calc.js), heat map, charts and explain popovers (extras.js), weekly recap (weekly.html)
.github/workflows/  the hourly schedule
```

Run locally: `pip install -r requirements.txt`, then `python -m app.run`. Use `--sample` for fake data without internet access.
