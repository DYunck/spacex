// SPCX options signals dashboard — reads data/latest.json written by the GitHub Action.
const $ = (id) => document.getElementById(id);
const fmt = (x, d = 2) => (x === null || x === undefined ? "—" : Number(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d }));
const money = (x, d = 2) => (x === null || x === undefined ? "—" : (x < 0 ? "−$" : "$") + fmt(Math.abs(x), d));
const pct = (x, d = 1) => (x === null || x === undefined ? "—" : (x > 0 ? "+" : "") + fmt(x, d) + "%");
const cls = (x) => (x > 0 ? "pos" : x < 0 ? "neg" : "muted");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();

let D = null;
let tf = "daily";
let sg = "calls";

function table(el, head, rows, empty = "Nothing to show yet.") {
  if (!rows.length) { el.outerHTML = `<div class="empty" id="${el.id}">${empty}</div>`; return; }
  if (el.tagName !== "TABLE") { const t = document.createElement("table"); t.id = el.id; el.replaceWith(t); el = t; }
  el.innerHTML = `<thead><tr>${head.map(([h, n]) => `<th class="${n ? "n" : ""}">${h}</th>`).join("")}</tr></thead>` +
    `<tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td class="${head[i][1] ? "n" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody>`;
}

function render() {
  const d = D;
  $("price").textContent = money(d.price);
  $("chg").innerHTML = `<span class="${cls(d.change_pct)}">${pct(d.change_pct, 2)}</span>`;
  const gen = new Date(d.generated);
  const ageMin = (Date.now() - gen) / 60000;
  $("updated").textContent = `Updated ${gen.toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}`;

  const banners = [];
  if (d.source.includes("SAMPLE")) banners.push("These are SAMPLE numbers for testing, not real market data. Real data appears after the first scheduled run.");
  const day = new Date().getDay();
  if (ageMin > 26 * 60 && day > 1 && day < 6) banners.push("Data is more than a day old — the scheduled update may have stopped. Check the Actions tab on GitHub.");
  $("banners").innerHTML = banners.map((b) => `<div class="banner warn">${esc(b)}</div>`).join("");

  $("today").textContent = d.today_paragraph || "";

  // hero
  const s = d.direction.score;
  $("stance").textContent = d.stance.action;
  $("stance").className = "stance " + (s >= 20 ? "up" : s <= -20 ? "down" : "");
  $("detail").textContent = d.stance.detail;
  $("needle").style.left = `${(s + 100) / 2}%`;
  $("scoreTxt").innerHTML = `<b>${d.direction.label} ${s > 0 ? "+" : ""}${s}</b> · strong at ±${d.signal_min_score}`;

  const v = d.volatility;
  const chips = [
    `<span class="chip ${s >= 20 ? "up" : s <= -20 ? "down" : ""}">${esc(d.direction.label)}</span>`,
    `<span class="chip ${v.verdict === "expensive" ? "warn" : v.verdict === "cheap" ? "up" : ""}">Options ${esc(v.verdict)}</span>`,
  ];
  if (d.next_big_event) chips.push(`<span class="chip warn">${esc(d.next_big_event.title.split(" — ")[0])}: ${d.next_big_event.days === 0 ? "today" : "in " + d.next_big_event.days + "d"}</span>`);
  $("chips").innerHTML = chips.join("");

  const em = d.expected_move;
  $("glance").innerHTML = [
    ["Previous close", money(d.prev_close)],
    ["IPO price", money(d.ipo_price)],
    ["Range since IPO", `${money(d.low_since_ipo)} – ${money(d.high_since_ipo)}`],
    ["Daily score / hourly score", `${d.direction.daily_score} / ${d.direction.hourly_score}`],
    em ? [`Expected move by ${em.expiry}`, `±${money(em.dollars)} (±${em.pct}%)`] : null,
  ].filter(Boolean).map(([k, val]) => `<dt>${k}</dt><dd>${val}</dd>`).join("");

  $("reasons").innerHTML = d.direction.reasons.map((r) =>
    `<li><span class="pts ${cls(r.points)}">${r.points > 0 ? "+" : ""}${fmt(r.points, 0)}</span><span>${esc(r.text)}</span></li>`).join("") ||
    `<li class="muted">Not enough data yet.</li>`;

  // daily vs hourly
  const ds = d.daily_snapshot, hs = d.hourly_snapshot || {};
  const row = (name, key, f) => [name, f(ds[key]), f(hs[key])];
  const rsiTxt = (x) => x == null ? "—" : `${fmt(x, 0)} ${x > 70 ? "(overbought)" : x < 30 ? "(oversold)" : ""}`;
  table($("tf"), [["", 0], ["Daily", 1], ["Hourly", 1]], [
    row("Price", "Close", money),
    row("20-bar average", "sma20", money),
    row("50-bar average", "sma50", money),
    row("RSI (14)", "rsi", rsiTxt),
    row("MACD histogram", "macd_hist", (x) => `<span class="${cls(x)}">${fmt(x)}</span>`),
    row("Bollinger upper", "bb_up", money),
    row("Bollinger lower", "bb_low", money),
    row("Avg true range", "atr", money),
    row("Volume vs. normal", "volume_vs_avg", (x) => x == null ? "—" : fmt(x, 1) + "×"),
    row("Actual volatility (annual)", "rvol20", (x) => x == null ? "—" : fmt(x * 100, 0) + "%"),
  ]);

  // volatility
  $("vol").innerHTML = [
    ["Implied volatility (at the money)", v.atm_iv == null ? "—" : `${v.atm_iv}%`],
    ["Actual volatility (20 days)", v.realized_vol == null ? "—" : `${v.realized_vol}%`],
    ["Implied ÷ actual", v.iv_rv_ratio == null ? "—" : `${v.iv_rv_ratio}×`],
    ["IV rank (0 = cheapest, 100 = priciest)", v.iv_rank == null ? `building history (${v.iv_history_days}/20 days)` : v.iv_rank],
  ].map(([k, val]) => `<dt>${k}</dt><dd>${val}</dd>`).join("");
  $("volnotes").innerHTML = v.notes.map((n) => `<p class="note">• ${esc(n)}</p>`).join("") +
    `<p class="note">Implied volatility is how much movement option prices assume. When it's much higher than the stock's actual movement, option buyers are overpaying.</p>`;

  renderSugg();

  // events
  const evColor = { earnings: "var(--accent)", lockup: "var(--down)", macro: "var(--warn)", opex: "var(--muted)" };
  table($("events"), [["Date", 0], ["", 0], ["Event", 0], ["In", 1]],
    d.events.map((e) => [e.date, `<span class="ev-type" style="color:${evColor[e.type] || "var(--muted)"}">${esc(e.type)}</span>`,
      esc(e.title) + (e.verified === false ? ' <span class="muted">(unconfirmed)</span>' : ""),
      e.days < 0 ? `<span class="muted">${-e.days}d ago</span>` : e.days === 0 ? "today" : `${e.days}d`]));

  // flow
  const f = d.flow || {};
  $("flow").innerHTML = [
    ["Call volume today", fmt(f.call_volume, 0)], ["Put volume today", fmt(f.put_volume, 0)],
    ["Put/call ratio (volume)", fmt(f.pc_volume)], ["Put/call ratio (open interest)", fmt(f.pc_open_interest)],
  ].map(([k, val]) => `<dt>${k}</dt><dd>${val}</dd>`).join("");
  table($("unusual"), [["Unusual activity", 0], ["Volume", 1], ["Open int.", 1], ["Price", 1]],
    (f.unusual || []).map((u) => [esc(u.contract), fmt(u.volume, 0), fmt(u.open_interest, 0), money(u.mid)]),
    "No unusual activity (volume more than 2× open interest) right now.");

  // context
  table($("context"), [["", 0], ["Last", 1], ["Today", 1], ["20 days", 1]],
    Object.entries(d.context).map(([k, c]) => [`${esc(c.name)}${c.corr_60d != null ? ` <span class="muted">(moves with SPCX: ${fmt(c.corr_60d)})</span>` : ""}`,
      fmt(c.last), `<span class="${cls(c.change_pct)}">${pct(c.change_pct)}</span>`, `<span class="${cls(c.change_20d_pct)}">${pct(c.change_20d_pct)}</span>`]));
  $("levels").innerHTML = d.levels.map((l) => `<span class="chip ${l.kind === "support" ? "up" : l.kind === "resistance" ? "down" : ""}">${esc(l.kind)} ${money(l.price)}</span>`).join("");

  // backtest
  const bt = d.backtest;
  table($("bt"), [["Timeframe", 0], ["Signal", 0], ["Look-ahead", 0], ["Times fired", 1], ["Right direction", 1], ["Avg move", 1], ["Worst", 1], ["Best", 1]],
    bt.rows.map((r) => [r.timeframe, r.signal, r.horizon, r.count, r.win_rate == null ? "—" : r.win_rate + "%",
      r.avg_move_pct == null ? "—" : `<span class="${cls(r.avg_move_pct)}">${pct(r.avg_move_pct, 2)}</span>`,
      r.worst_pct == null ? "—" : pct(r.worst_pct, 2), r.best_pct == null ? "—" : pct(r.best_pct, 2)]));
  $("btnote").textContent = `${bt.note} Tested over ${bt.trading_days} trading days at a score of ±${bt.threshold} (single timeframe). "Avg move" is the stock's move in the signal's direction.`;

  // strong-signal history
  const t = d.track_record;
  $("track").innerHTML = `<span class="chip">${t.signals} strong signals logged</span>` +
    (t.right_5d_pct != null ? `<span class="chip ${t.right_5d_pct >= 50 ? "up" : "down"}">Right after 5 days: ${t.right_5d_pct}% of ${t.graded_5d}</span>` : `<span class="chip">Results appear 5 trading days after each signal</span>`);
  fetch("data/signals.json?ts=" + Date.now()).then((r) => r.ok ? r.json() : []).catch(() => []).then((log) => {
    const res = (x, ok) => x == null ? "—" : `<span class="${ok ? "pos" : "neg"}">${pct(x, 1)}</span>`;
    table($("signals"), [["When", 0], ["Signal", 0], ["Price", 1], ["After 1 day", 1], ["After 5 days", 1], ["After 10 days", 1]],
      log.slice().reverse().slice(0, 50).map((a) => [new Date(a.time).toLocaleString([], { dateStyle: "short", timeStyle: "short" }),
        `<span class="${a.direction === "up" ? "pos" : "neg"}">${esc(a.label)} (${a.score > 0 ? "+" : ""}${a.score})</span>`,
        money(a.price), res(a.after_1d, a.right_1d), res(a.after_5d, a.right_5d), res(a.after_10d, a.right_10d)]),
      "No strong signals yet. Each time the score crosses ±40 it's logged here with how the stock moved afterward.");
  });

  renderEventMoves(d);
  renderGrades(d);
  if (window.Calc) window.Calc.init(d);

  $("footsrc").textContent = `Data: ${d.source}. Prices may be delayed ~15 minutes. Updates hourly during market hours.`;
  drawChart();
}

function renderSugg() {
  const list = D.suggestions[sg] || [];
  table($("sugg"), [["Contract", 0], ["", 0], ["Price (mid)", 1], ["Cost / max loss", 1], ["Breakeven", 1], ["Delta", 1], ["Decay/day", 1], ["IV", 1], ["Spread", 1], ["Open int.", 1], ["Heads-up", 0]],
    list.map((c) => [esc(c.contract), `<button class="try" data-exp="${c.expiry}" data-k="${c.strike}" data-t="${sg === "calls" ? "c" : "p"}">Try it</button>`, money(c.mid), money(c.cost, 0), money(c.breakeven), fmt(c.delta), money(c.theta_per_day),
      c.iv + "%", c.spread_pct + "%", fmt(c.open_interest, 0),
      c.events_before_expiry.length ? `<span class="chip warn" title="${esc(c.events_before_expiry.join("; "))}">${c.events_before_expiry.length} event(s) before expiry</span>` : ""]),
    "No contracts pass the liquidity filters right now.");
}

function renderEventMoves(d) {
  const em = d.event_moves || { rows: [], summary: {} };
  const su = em.summary || {};
  const chips = [];
  if (su.earnings_count) chips.push(`<span class="chip">Earnings: average move ±${su.earnings_avg_abs_move}% (${su.earnings_count} reports)</span>`);
  if (su.lockup_count) chips.push(`<span class="chip ${su.lockup_avg_move >= 0 ? "up" : "down"}">Lockup days: average ${pct(su.lockup_avg_move)} (${su.lockup_count})</span>`);
  if (su.priced_in_compared) chips.push(`<span class="chip warn">Smaller than priced in: ${su.smaller_than_priced} of ${su.priced_in_compared}</span>`);
  $("em-summary").innerHTML = chips.join("");
  table($("em-table"), [["Date", 0], ["", 0], ["Event", 0], ["Next-day move", 1], ["3-day move", 1], ["Priced in", 1], ["Compared", 0]],
    em.rows.map((r) => [r.date, `<span class="ev-type" style="color:${r.type === "earnings" ? "var(--accent)" : "var(--down)"}">${esc(r.type)}</span>`, esc(r.title),
      `<span class="${cls(r.move_1d_pct)}">${pct(r.move_1d_pct)}</span>`,
      r.move_3d_pct == null ? "—" : `<span class="${cls(r.move_3d_pct)}">${pct(r.move_3d_pct)}</span>`,
      r.implied_pct == null ? '<span class="muted">not recorded</span>' : `±${fmt(r.implied_pct, 1)}%`,
      r.vs_implied ? `<span class="chip ${r.vs_implied.startsWith("smaller") ? "up" : "warn"}">${esc(r.vs_implied)}</span>` : ""]),
    "No past earnings or lockup dates yet.");
}

let showFew = false;
function renderGrades(d) {
  const g = d.signal_grades || { rows: [] };
  const vClass = { Helpful: "up", Misleading: "down", "No edge": "", "Too few": "dim" };
  const count = (v) => g.rows.filter((r) => r.verdict === v).length;
  $("sg-summary").innerHTML = [["Helpful", "up"], ["No edge", ""], ["Misleading", "down"], ["Too few", "dim"]]
    .map(([v, c]) => `<span class="chip ${c}">${v}: ${count(v)}</span>`).join("");
  table($("sg-table"), [["Signal", 0], ["Chart", 0], ["Predicts", 0], ["Checked after", 0], ["Times seen", 1], ["Right", 1], ["Avg move", 1], ["Verdict", 0]],
    g.rows.filter((r) => showFew || r.verdict !== "Too few").map((r) => [esc(r.signal), r.timeframe, r.predicts === "up" ? '<span class="pos">Rise</span>' : '<span class="neg">Drop</span>', r.horizon, r.count,
      r.win_rate == null ? "—" : r.win_rate + "%", r.avg_move_pct == null ? "—" : `<span class="${cls(r.avg_move_pct)}">${pct(r.avg_move_pct, 2)}</span>`,
      `<span class="chip ${vClass[r.verdict]}">${r.verdict}</span>`]), "Every signal has fewer than 10 examples so far.");
  const few = count("Too few"), more = $("sg-more");
  more.hidden = !few;
  more.textContent = showFew ? "Hide signals with too few examples" : `Show ${few} more with too few examples`;
  more.onclick = () => { showFew = !showFew; renderGrades(d); };
  $("sg-note").textContent = (g.note || "") + ' "Avg move" is the stock\'s move in the predicted direction. A signal marked Misleading still counts in the score today; if it stays that way for months, it may be worth removing.';
}

// ---------------------------------------------------------------- install as an app
function setupInstall() {
  const box = $("install");
  if (!box) return;
  let dismissed = false;
  try { dismissed = localStorage.getItem("installHintDismissed") === "1"; } catch (e) { /* storage blocked */ }
  const standalone = window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  if (standalone || dismissed) return;
  const close = '<button class="x" aria-label="Dismiss">×</button>';
  const bind = () => box.querySelector(".x").addEventListener("click", () => {
    box.hidden = true;
    try { localStorage.setItem("installHintDismissed", "1"); } catch (e) { /* ignore */ }
  });
  const ios = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  if (ios) {
    box.innerHTML = `<span>📲 Put this on your Home Screen: open it in <b>Safari</b>, tap <b>Share</b> (the square with an arrow), then <b>Add to Home Screen</b>.</span>${close}`;
    box.hidden = false; bind();
  }
  window.addEventListener("beforeinstallprompt", (ev) => {
    ev.preventDefault();
    box.innerHTML = `<span>📲 Install this dashboard as an app.</span><button class="inst">Install</button>${close}`;
    box.hidden = false; bind();
    box.querySelector(".inst").addEventListener("click", () => { ev.prompt(); box.hidden = true; });
  });
}
setupInstall();
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("sw.js").catch(() => {}));
}

// ---------------------------------------------------------------- charts
let chart, rsiChart;
function drawChart() {
  const box = $("chart"), rbox = $("rsi");
  try { chart && chart.remove(); rsiChart && rsiChart.remove(); } catch (e) { /* already gone */ }
  chart = rsiChart = null;
  box.innerHTML = ""; rbox.innerHTML = "";
  if (!window.LightweightCharts) { box.innerHTML = '<div class="empty">Chart library failed to load. Try refreshing the page.</div>'; return; }
  try {
    drawChartInner(box, rbox);
  } catch (e) {
    console.error(e);
    box.innerHTML = `<div class="empty">The chart couldn't be drawn on this device (${esc(e.message || e)}). The rest of the dashboard is unaffected.</div>`;
    rbox.innerHTML = "";
  }
}

const hexA = (c, a) => (/^#[0-9a-f]{6}$/i.test(c) ? c + a : c);
const boxW = (el) => Math.max(200, Math.floor(el.getBoundingClientRect().width) || el.parentElement.clientWidth - 36 || 320);

function drawChartInner(box, rbox) {
  const bars = D[tf] || [];
  const muted = css("--muted") || "#5d6673", grid = css("--chart-grid") || "#eef0f3", lineC = css("--line") || "#e3e6eb";
  const opts = {
    width: boxW(box), height: box.clientHeight || 380,
    layout: { background: { type: "solid", color: "rgba(0,0,0,0)" }, textColor: muted, fontSize: 11 },
    grid: { vertLines: { color: grid }, horzLines: { color: grid } },
    rightPriceScale: { borderColor: lineC },
    timeScale: { borderColor: lineC, timeVisible: tf === "hourly", secondsVisible: false },
    crosshair: { mode: 0 },
    handleScroll: { vertTouchDrag: false },
  };
  chart = LightweightCharts.createChart(box, opts);
  const up = css("--up") || "#0f8a5f", down = css("--down") || "#c23b3b";
  const candles = chart.addCandlestickSeries({ upColor: up, downColor: down, wickUpColor: up, wickDownColor: down, borderVisible: false });
  candles.setData(bars.map((b) => ({ time: b.t, open: b.o, high: b.h, low: b.l, close: b.c })));
  const line = (key, color, w = 2, style = 0) => {
    const s = chart.addLineSeries({ color, lineWidth: w, lineStyle: style, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    s.setData(bars.filter((b) => b[key] != null).map((b) => ({ time: b.t, value: b[key] })));
  };
  line("sma20", "#2457d6"); line("sma50", "#c77800");
  line("bb_up", "#9aa3ae", 1, 2); line("bb_low", "#9aa3ae", 1, 2);
  const vol = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
  chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
  vol.setData(bars.map((b) => ({ time: b.t, value: b.v, color: b.c >= b.o ? hexA(up, "55") : hexA(down, "55") })));
  for (const l of D.levels) {
    candles.createPriceLine({ price: l.price, color: l.kind === "IPO price" ? (css("--accent") || "#2457d6") : "#888888", lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: l.kind === "IPO price" ? "IPO" : "" });
  }
  chart.timeScale().fitContent();

  rsiChart = LightweightCharts.createChart(rbox, { ...opts, height: rbox.clientHeight || 110, timeScale: { ...opts.timeScale, visible: false } });
  const r = rsiChart.addLineSeries({ color: "#8a5cf6", lineWidth: 2, priceLineVisible: false });
  r.setData(bars.filter((b) => b.rsi != null).map((b) => ({ time: b.t, value: b.rsi })));
  r.createPriceLine({ price: 70, color: down, lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
  r.createPriceLine({ price: 30, color: up, lineWidth: 1, lineStyle: 2, axisLabelVisible: false });
  rsiChart.timeScale().fitContent();
  chart.timeScale().subscribeVisibleLogicalRangeChange((rg) => rg && rsiChart && rsiChart.timeScale().setVisibleLogicalRange(rg));
}

// Keep the chart sized to its box (rotation, window resize)
let lastW = 0, resizeT;
window.addEventListener("resize", () => {
  clearTimeout(resizeT);
  resizeT = setTimeout(() => {
    if (!chart) return;
    const w = boxW($("chart"));
    if (Math.abs(w - lastW) < 2) return;
    lastW = w;
    chart.applyOptions({ width: w }); rsiChart && rsiChart.applyOptions({ width: w });
  }, 150);
});

document.querySelectorAll("[data-tf]").forEach((b) => b.addEventListener("click", () => {
  tf = b.dataset.tf;
  document.querySelectorAll("[data-tf]").forEach((x) => x.classList.toggle("on", x === b));
  drawChart();
}));
document.querySelectorAll("[data-sg]").forEach((b) => b.addEventListener("click", () => {
  sg = b.dataset.sg;
  document.querySelectorAll("[data-sg]").forEach((x) => x.classList.toggle("on", x === b));
  renderSugg();
}));

fetch("data/latest.json?ts=" + Date.now())
  .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then((d) => { D = d; render(); })
  .catch((e) => { $("updated").textContent = "No data yet"; $("banners").innerHTML = `<div class="banner warn">No data yet (${esc(e.message)}). The first update runs on GitHub — check the Actions tab.</div>`; });

// Reload every 10 minutes so an open tab stays fresh
setInterval(() => location.reload(), 10 * 60 * 1000);
