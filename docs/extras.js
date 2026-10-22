// Explain-this popovers, option chain heat map, launches, headlines, comparison and volatility charts.
(function () {
  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (x, d = 2) => Number(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 1) => (x == null ? "—" : (x > 0 ? "+" : "") + fmt(x, d) + "%");
  const cls = (x) => (x > 0 ? "pos" : x < 0 ? "neg" : "muted");
  let D;

  // ------------------------------------------------------------ explain-this
  const EX = {
    starship: ["Starship flight tracker", "Every Starship test flight with its result, and how SPCX moved afterward. Flights during market hours are compared with that day's close; flights after the close or on weekends are compared with the next trading day."],
    lockups: ["Insider selling (lockups)", "Shares held by employees, early investors and Elon Musk can't be sold until set dates after the IPO. Each unlock adds shares that could be sold, which can weigh on the price, but SPCX's reaction on past unlock days has been mixed."],
    tradable: ["Freely tradable shares", "Shares that anyone can buy or sell today: the shares sold at the IPO plus every lockup tranche already released. The rest are still restricted."],
    analysts: ["Analyst price targets", "Where Wall Street analysts think SPCX will trade in about 12 months. The bar runs from the lowest to the highest target; the marker shows today's price. Targets are opinions and are often wrong."],
    rating: ["Consensus rating", "The average analyst recommendation on a 1–5 scale: 1 = strong buy, 3 = hold, 5 = sell."],
    today: ["Today in one paragraph", "A plain-English summary written automatically from the numbers on this page each hour. Nothing in it is a prediction or advice."],
    score: ["Direction score", "Adds up points from about a dozen chart signals, from −100 (bearish) to +100 (bullish). ±40 or more counts as a strong signal. It describes current conditions; it doesn't predict the future."],
    why: ["Why", "Every signal that went into the score, sorted by size. Green numbers push toward bullish, red toward bearish. Check \"Which signals have actually worked\" to see how much to trust each one."],
    tf: ["Daily vs. hourly", "The same indicators measured on daily bars (the bigger picture) and hourly bars (the last few days). When the two disagree, signals are less reliable."],
    iv: ["Implied volatility (IV)", "How much movement option prices assume, as a yearly percentage. Higher IV means more expensive options. 60% IV implies a typical move of about ±3.8% per day."],
    realvol: ["Actual volatility", "How much SPCX really moved over the last 20 trading days, on the same yearly scale as implied volatility, so the two can be compared."],
    ivratio: ["Implied ÷ actual", "Option prices divided by real movement. Above 1.3× means options are pricey compared with how the stock actually moves; below 0.9× means they're relatively cheap."],
    ivrank: ["IV rank", "Where today's implied volatility sits in its own past range: 0 is the cheapest options have been, 100 the most expensive. It needs 20 trading days of collected history."],
    ivhist: ["Option prices over time", "Implied volatility (what options assume) against actual volatility (what the stock did). Implied usually rises into earnings and drops right after; that drop is the volatility crush."],
    expmove: ["Expected move", "How far the options market thinks SPCX could move by a date, worked out from option prices. The stock usually ends up inside this range about two-thirds of the time."],
    contracts: ["Contracts worth a look", "A few options that are easy to trade (tight bid/ask, real open interest) with a delta near 0.45. Starting points to research, not recommendations."],
    mid: ["Mid price", "Halfway between the bid (what buyers pay) and the ask (what sellers want). Prices are per share; one contract covers 100 shares."],
    cost: ["Cost / max loss", "What one contract costs (mid price × 100). If you buy an option, this is the most you can lose."],
    breakeven: ["Breakeven", "Where SPCX has to be at expiration for the option to be worth what you paid: strike plus the price for a call, strike minus the price for a put."],
    delta: ["Delta", "How much the option's price moves when SPCX moves $1. A 0.45 delta gains about $0.45 per share ($45 per contract) for each $1 rise. It's also a rough chance of finishing in the money."],
    decay: ["Decay per day (theta)", "Roughly how much one contract loses each day just from time passing, if nothing else changes. It speeds up in the last three weeks."],
    spread: ["Bid/ask spread", "The gap between buying and selling prices, as a % of the mid price. Under 5% is good. A 15% spread means you start 15% behind."],
    oi: ["Open interest", "How many of these contracts currently exist. Higher open interest usually means easier, cheaper trading."],
    volume: ["Volume", "How many contracts traded today."],
    calc: ["Payoff calculator", "Estimates an option's value at different SPCX prices and dates using the Black-Scholes model. Use the sliders to see time decay and volatility crush. Real prices will differ."],
    heatmap: ["Option chain heat map", "Every strike and expiration in one grid. Cells with stronger color have more contracts traded today (volume) or outstanding (open interest), showing where traders are placing their bets."],
    events: ["Upcoming events", "Dates that can move SPCX or its option prices: earnings, lockups (insiders allowed to sell), Fed meetings, options expirations and big launches."],
    levels: ["Support and resistance", "Prices where SPCX has repeatedly turned around before. Support is where buyers stepped in; resistance is where sellers did. The $135 IPO price is watched by many traders."],
    launches: ["Upcoming launches", "SpaceX's scheduled launches. Starship test flights and other big missions can move the stock, especially if something goes very right or very wrong."],
    compare: ["SPCX vs. Tesla vs. Nasdaq-100", "Percentage change from the start of the chosen period. If all three move together, the move is probably about the whole market, not SpaceX."],
    eventmoves: ["Moves around past events", "What SPCX actually did after each earnings report and lockup date, compared with the move options priced in beforehand."],
    putcall: ["Put/call ratio", "Puts traded divided by calls traded. Below 0.7 means traders mostly bet on a rise; above 1.0 means mostly bets on a drop or buying protection."],
    backtest: ["Backtest", "How the scoring rules would have done on SPCX's past prices. \"Right direction\" near 50% is a coin flip."],
    grades: ["Signal grades", "Each signal tested on its own against SPCX's history. Helpful = right at least 58% of the time with a positive average move. Misleading = wrong more often than right."],
    history: ["Strong-signal history", "Every time the score crossed ±40 during market hours, with how SPCX moved 1, 5 and 10 trading days later."],
    rsi: ["RSI (Relative Strength Index)", "A 0–100 momentum gauge. Above 70 = overbought (a pullback is more likely); below 30 = oversold (a bounce is more likely)."],
    macd: ["MACD", "A momentum indicator from two moving averages. Positive means upward momentum; crossing from negative to positive is a classic buy signal, and the reverse a sell signal."],
    bollinger: ["Bollinger bands", "A band around the 20-bar average, two standard deviations wide. Closing outside the band means the price is stretched and often snaps back."],
    atr: ["Average true range", "The typical size of one bar's high-to-low swing, in dollars. A rough measure of how much SPCX moves in a day (or hour)."],
    sma20: ["20-bar average", "The average closing price over the last 20 bars (days or hours). Price above it is a sign of a short-term uptrend."],
    sma50: ["50-bar average", "The average closing price over the last 50 bars. When the 20-bar average is above the 50-bar, the longer trend is up."],
    volnormal: ["Volume vs. normal", "Today's trading volume compared with the 20-bar average. 2× means twice the usual activity, so something is happening."],
  };
  // label text on the page -> glossary key
  const LABELS = [
    ["Implied volatility (at the money)", "iv"], ["Actual volatility (20 days)", "realvol"], ["Implied ÷ actual", "ivratio"],
    ["IV rank", "ivrank"], ["Daily score / hourly score", "tf"], ["Expected move", "expmove"], ["Put/call ratio", "putcall"],
    ["Price (mid)", "mid"], ["Cost / max loss", "cost"], ["Breakeven", "breakeven"], ["Delta", "delta"], ["Decay/day", "decay"],
    ["IV", "iv"], ["Spread", "spread"], ["Open int.", "oi"], ["Priced in", "expmove"],
    ["RSI (14)", "rsi"], ["MACD histogram", "macd"], ["Bollinger upper", "bollinger"], ["Bollinger lower", "bollinger"],
    ["Avg true range", "atr"], ["20-bar average", "sma20"], ["50-bar average", "sma50"], ["Volume vs. normal", "volnormal"],
    ["Actual volatility (annual)", "realvol"],
  ];
  const btn = (k) => `<button class="ex" data-ex="${k}" aria-label="Explain">i</button>`;
  function decorate(root) {
    (root || document).querySelectorAll("dt, th, #tf td:first-child").forEach((el) => {
      if (el.querySelector(".ex")) return;
      const t = el.textContent.trim();
      const hit = LABELS.find(([label]) => t === label || (label.length > 8 && t.startsWith(label)));
      if (hit) el.insertAdjacentHTML("beforeend", " " + btn(hit[1]));
    });
  }
  const pop = () => $("ex-pop");
  function openPop(b) {
    const e = EX[b.dataset.ex]; if (!e) return;
    const p = pop();
    p.innerHTML = `<strong>${esc(e[0])}</strong><p>${esc(e[1])}</p><button class="ex-close" aria-label="Close">×</button>`;
    p.hidden = false;
    const r = b.getBoundingClientRect(), vw = document.documentElement.clientWidth;
    const w = Math.min(320, vw - 24);
    p.style.width = w + "px";
    p.style.left = Math.max(12, Math.min(r.left + r.width / 2 - w / 2, vw - w - 12)) + "px";
    const below = r.bottom + 8, ph = p.offsetHeight;
    p.style.top = (below + ph > window.innerHeight - 8 && r.top - ph - 8 > 8 ? r.top - ph - 8 : below) + "px";
    p.dataset.for = b.dataset.ex;
  }
  document.addEventListener("click", (ev) => {
    const b = ev.target.closest("button.ex");
    if (b) { ev.preventDefault(); ev.stopPropagation(); if (!pop().hidden && pop().dataset.for === b.dataset.ex) { pop().hidden = true; } else openPop(b); return; }
    if (!ev.target.closest("#ex-pop") || ev.target.closest(".ex-close")) pop().hidden = true;
  }, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") pop().hidden = true; });
  window.addEventListener("scroll", () => { if (!pop().hidden) pop().hidden = true; }, { passive: true });

  // ------------------------------------------------------------ heat map
  let hmType = "c", hmMetric = "v";
  const short = (n) => (n >= 10000 ? Math.round(n / 1000) + "k" : n >= 1000 ? (n / 1000).toFixed(1) + "k" : String(n));
  function renderHeatmap() {
    const chain = (D.chain || []).filter((o) => o.t === hmType);
    const el = $("heatmap");
    if (!chain.length) { el.innerHTML = '<tbody><tr><td class="empty">No option data in this update.</td></tr></tbody>'; return; }
    const spot = D.price;
    const exps = [...new Set(chain.map((o) => o.e))].sort();
    const strikes = [...new Set(chain.filter((o) => o.k >= spot * 0.75 && o.k <= spot * 1.25).map((o) => o.k))].sort((a, b) => b - a);
    const map = new Map(chain.map((o) => [o.e + "|" + o.k, o]));
    const val = (o) => (o ? (hmMetric === "v" ? o.v || 0 : o.oi || 0) : 0);
    let max = 0;
    for (const e of exps) for (const k of strikes) max = Math.max(max, val(map.get(e + "|" + k)));
    const atm = strikes.reduce((a, b) => (Math.abs(b - spot) < Math.abs(a - spot) ? b : a), strikes[0]);
    const color = hmType === "c" ? "63,160,120" : "214,84,84";
    const head = `<thead><tr><th>Strike</th>${exps.map((e) => {
      const [y, m, d] = e.split("-").map(Number); const dt = new Date(y, m - 1, d);
      return `<th class="n">${dt.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</th>`;
    }).join("")}</tr></thead>`;
    const body = strikes.map((k) => {
      const cells = exps.map((e) => {
        const o = map.get(e + "|" + k), v = val(o);
        if (!o) return '<td class="hm-empty"></td>';
        const a = max ? Math.sqrt(v / max) : 0;
        const dark = a > 0.55;
        return `<td class="hm-cell${dark ? " hm-dark" : ""}" style="background:rgba(${color},${(0.06 + a * 0.88).toFixed(3)})" data-e="${e}" data-k="${k}" title="${esc(`$${k} ${hmType === "c" ? "call" : "put"} ${e}: volume ${o.v}, open interest ${o.oi}, mid $${o.m}`)}">${v ? short(v) : "·"}</td>`;
      }).join("");
      const kTxt = "$" + fmt(k, k % 1 ? 1 : 0);
      return `<tr class="${k === atm ? "hm-atm" : ""}"><th>${kTxt}${k === atm ? ' <span class="hm-now">≈ now</span>' : ""}</th>${cells}</tr>`;
    }).join("");
    el.innerHTML = head + `<tbody>${body}</tbody>`;
  }
  function bindSeg(id, set) {
    document.querySelectorAll(`#${id} button`).forEach((b) => b.addEventListener("click", () => {
      document.querySelectorAll(`#${id} button`).forEach((x) => x.classList.toggle("on", x === b));
      set(b.dataset.v); renderHeatmap();
    }));
  }
  bindSeg("hm-type", (v) => (hmType = v));
  bindSeg("hm-metric", (v) => (hmMetric = v));
  $("heatmap").addEventListener("click", (e) => {
    const td = e.target.closest("td.hm-cell");
    if (td && window.Calc && window.Calc.load) window.Calc.load(hmType, td.dataset.e, Number(td.dataset.k));
  });

  // ------------------------------------------------------------ launches & news
  function renderLaunches() {
    const L = D.launches || [];
    const el = $("launches");
    if (!L.length) { el.outerHTML = '<div class="empty" id="launches">No launch schedule available right now.</div>'; return; }
    const statusCls = (s) => (s === "Go" ? "up" : s === "Hold" ? "down" : "dim");
    el.innerHTML = `<thead><tr><th>When</th><th>Mission</th><th>Status</th></tr></thead><tbody>` + L.slice(0, 10).map((x) => {
      const t = new Date(x.net);
      const when = t.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }) + "<br><span class=\"muted\">" +
        t.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) + "</span>";
      const name = esc(x.name.replace(" Block 5", "").replace(" | ", ": "));
      return `<tr class="${x.notable ? "launch-big" : ""}"><td>${when}</td><td>${x.notable ? "★ " : ""}${name}<br><span class="muted">${esc(x.location || x.pad || "")}</span></td>` +
        `<td><span class="chip ${statusCls(x.status)}">${esc(x.status || "TBD")}</span></td></tr>`;
    }).join("") + "</tbody>";
  }
  function ago(iso) {
    const t = new Date(iso); if (isNaN(t)) return "";
    const m = Math.round((Date.now() - t) / 60000);
    if (m < 60) return `${Math.max(1, m)} min ago`;
    if (m < 60 * 24) return `${Math.round(m / 60)} hr ago`;
    return t.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  }
  function renderNews() {
    const N = D.news || [];
    $("news").innerHTML = N.length ? N.map((n) =>
      `<li><a href="${esc(n.url)}" target="_blank" rel="noopener noreferrer">${esc(n.title)}</a><span class="muted">${esc(n.publisher)}${n.time ? " · " + ago(n.time) : ""}</span></li>`).join("")
      : '<li class="muted">No headlines available right now.</li>';
  }

  // ------------------------------------------------------------ small charts
  const charts = {};
  const boxW = (el) => Math.max(200, Math.floor(el.getBoundingClientRect().width) || 320);
  function baseOpts(el, pctScale) {
    return {
      width: boxW(el), height: el.clientHeight || 240,
      layout: { background: { type: "solid", color: "rgba(0,0,0,0)" }, textColor: css("--muted"), fontSize: 11 },
      grid: { vertLines: { color: css("--chart-grid") }, horzLines: { color: css("--chart-grid") } },
      rightPriceScale: { borderColor: css("--line") }, timeScale: { borderColor: css("--line") },
      crosshair: { mode: 0 }, handleScroll: { vertTouchDrag: false },
      localization: pctScale ? { priceFormatter: (v) => (v > 0 ? "+" : "") + v.toFixed(0) + "%" } : undefined,
    };
  }
  function fresh(id) {
    const el = $(id);
    try { charts[id] && charts[id].remove(); } catch (e) { /* ignore */ }
    el.innerHTML = "";
    return el;
  }
  let cmpRange = 63;
  function renderCompare() {
    const el = fresh("cmpchart");
    if (!window.LightweightCharts) { el.innerHTML = '<div class="empty">Chart library failed to load.</div>'; return; }
    const rows = (D.compare || []).slice(-cmpRange);
    if (rows.length < 2) { el.innerHTML = '<div class="empty">Not enough history yet.</div>'; return; }
    try {
      const ch = LightweightCharts.createChart(el, baseOpts(el, true));
      charts.cmpchart = ch;
      const last = {};
      [["s", "#2457d6", 3], ["tsla", "#e0703a", 2], ["qqq", "#3aa17e", 2]].forEach(([k, color, w]) => {
        const base = rows.find((r) => r[k] != null);
        if (!base) return;
        const data = rows.filter((r) => r[k] != null).map((r) => ({ time: r.t, value: (r[k] / base[k] - 1) * 100 }));
        ch.addLineSeries({ color, lineWidth: w, priceLineVisible: false, lastValueVisible: true }).setData(data);
        last[k] = data[data.length - 1].value;
      });
      ch.timeScale().fitContent();
      const label = cmpRange >= 9999 ? "Since the IPO" : cmpRange === 21 ? "Over the last month" : "Over the last 3 months";
      $("cmp-note").innerHTML = `${label}: SPCX <b class="${cls(last.s)}">${pct(last.s)}</b>, Tesla <b class="${cls(last.tsla)}">${pct(last.tsla)}</b>, Nasdaq-100 <b class="${cls(last.qqq)}">${pct(last.qqq)}</b>.`;
    } catch (e) { el.innerHTML = `<div class="empty">Chart couldn't be drawn (${esc(e.message)}).</div>`; }
  }
  document.querySelectorAll("#cmp-range button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll("#cmp-range button").forEach((x) => x.classList.toggle("on", x === b));
    cmpRange = Number(b.dataset.r); renderCompare();
  }));

  function renderVolChart() {
    const el = fresh("volchart");
    if (!window.LightweightCharts) { el.innerHTML = '<div class="empty">Chart library failed to load.</div>'; return; }
    const rv = D.vol_history || [], iv = (D.iv_history || []).map((h) => ({ time: h.date, value: h.iv * 100 }));
    if (rv.length < 2) { el.innerHTML = '<div class="empty">Not enough history yet.</div>'; return; }
    try {
      const ch = LightweightCharts.createChart(el, baseOpts(el, false));
      charts.volchart = ch;
      const rvS = ch.addLineSeries({ color: "#8a95a5", lineWidth: 2, priceLineVisible: false, lastValueVisible: false,
        priceFormat: { type: "custom", formatter: (v) => v.toFixed(0) + "%" } });
      rvS.setData(rv.map((r) => ({ time: r.t, value: r.rv })));
      const ivS = ch.addLineSeries({ color: "#e0703a", lineWidth: 3, priceLineVisible: false, pointMarkersVisible: true,
        priceFormat: { type: "custom", formatter: (v) => v.toFixed(0) + "%" } });
      ivS.setData(iv);
      const days = new Set(rv.map((r) => r.t));
      const markers = (D.event_moves && D.event_moves.rows || []).filter((r) => days.has(r.date)).map((r) => ({
        time: r.date, position: "aboveBar", shape: "circle", color: r.type === "earnings" ? css("--accent") : css("--down"),
        text: r.type === "earnings" ? "E" : "L" })).sort((a, b) => (a.time < b.time ? -1 : 1));
      rvS.setMarkers(markers);
      ch.timeScale().fitContent();
      $("volchart-note").textContent = iv.length < 5
        ? `Implied volatility is collected once per trading day starting Oct 21, 2026 (${iv.length} so far), so the orange line grows over time. The gray line uses SPCX's full price history.`
        : `Orange above gray means options are pricing in more movement than the stock has actually shown.`;
    } catch (e) { el.innerHTML = `<div class="empty">Chart couldn't be drawn (${esc(e.message)}).</div>`; }
  }
  let rt;
  window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => { if (D) { renderCompare(); renderVolChart(); } }, 200); });

  // decorate tables that get re-rendered (tabs, toggles)
  const mo = new MutationObserver(() => { clearTimeout(mo.t); mo.t = setTimeout(() => decorate(), 50); });

  window.Extras = {
    init(data) {
      D = data;
      renderHeatmap(); renderLaunches(); renderNews(); renderCompare(); renderVolChart();
      decorate();
      mo.observe(document.querySelector(".wrap"), { childList: true, subtree: true });
    },
  };
})();
