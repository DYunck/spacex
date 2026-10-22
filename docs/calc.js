// "What if" payoff calculator for SPCX options. Pure estimates (Black-Scholes); never trades.
(function () {
  const $ = (id) => document.getElementById(id);
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const fmt = (x, d = 2) => Number(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const money = (x, d = 0) => (x < 0 ? "−$" : "$") + fmt(Math.abs(x), d);
  const signed = (x, d = 0) => { const r = Number(x.toFixed(d)); return (r > 0 ? "+" : r < 0 ? "−" : "") + "$" + fmt(Math.abs(r), d); };
  function niceTicks(min, max, n) {
    const raw = (max - min) / n, mag = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / mag;
    const step = (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * mag;
    const out = [];
    for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(v);
    return out;
  }
  const DAY = 86400000;

  // --- Black-Scholes
  function ncdf(x) {
    // Abramowitz-Stegun 7.1.26 via erf
    const t = 1 / (1 + 0.3275911 * Math.abs(x) / Math.SQRT2);
    const y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * Math.exp(-(x * x) / 2);
    return x >= 0 ? (1 + y) / 2 : (1 - y) / 2;
  }
  function bs(S, K, T, iv, type, r) {
    if (T <= 0 || iv <= 0) return Math.max(0, type === "c" ? S - K : K - S);
    const sq = Math.sqrt(T);
    const d1 = (Math.log(S / K) + (r + iv * iv / 2) * T) / (iv * sq);
    const d2 = d1 - iv * sq;
    return type === "c" ? S * ncdf(d1) - K * Math.exp(-r * T) * ncdf(d2) : K * Math.exp(-r * T) * ncdf(-d2) - S * ncdf(-d1);
  }

  let D, chain = [], st = null;
  const parseDate = (s) => { const [y, m, d] = s.split("-").map(Number); return new Date(y, m - 1, d); };
  const addDays = (dt, n) => new Date(dt.getFullYear(), dt.getMonth(), dt.getDate() + n);
  const dateTxt = (dt) => dt.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });

  function opts(type, exp) { return chain.filter((o) => o.t === type && o.e === exp).sort((a, b) => a.k - b.k); }
  function find(type, exp, k) { return chain.find((o) => o.t === type && o.e === exp && o.k === k); }
  function fallbackIv() { return (D.volatility && D.volatility.atm_iv ? D.volatility.atm_iv / 100 : 0.6); }

  function setSeg(id, v) { document.querySelectorAll(`#${id} button`).forEach((b) => b.classList.toggle("on", b.dataset.v === v)); }

  function fillExp() {
    const exps = [...new Set(chain.map((o) => o.e))].sort();
    $("c-exp").innerHTML = exps.map((e) => `<option value="${e}">${parseDate(e).toLocaleDateString(undefined, { month: "short", day: "numeric" })} (${Math.round((parseDate(e) - parseDate(D.today)) / DAY)}d)</option>`).join("");
    if (!exps.includes(st.exp)) st.exp = exps.find((e) => (parseDate(e) - parseDate(D.today)) / DAY >= 14) || exps[0];
    $("c-exp").value = st.exp;
  }
  function nearest(list, k) { return list.reduce((a, b) => (Math.abs(b.k - k) < Math.abs(a.k - k) ? b : a), list[0]); }
  function fillStrikes(keepPrice) {
    const list = opts(st.type, st.exp);
    if (!list.length) { $("c-strike").innerHTML = ""; return; }
    if (!list.some((o) => o.k === st.k)) st.k = nearest(list, st.k ?? D.price).k;
    $("c-strike").innerHTML = list.map((o) => `<option value="${o.k}">$${fmt(o.k, o.k % 1 ? 1 : 0)} — $${fmt(o.m)}</option>`).join("");
    $("c-strike").value = st.k;
    if (!keepPrice) { st.price = find(st.type, st.exp, st.k).m; $("c-price").value = st.price.toFixed(2); }
    // spread short leg: higher strike for calls, lower for puts
    const shorts = list.filter((o) => (st.type === "c" ? o.k > st.k : o.k < st.k));
    $("c-short-label").textContent = st.type === "c" ? "Sell the higher strike" : "Sell the lower strike";
    if (!shorts.some((o) => o.k === st.short)) {
      const target = st.type === "c" ? st.k * 1.1 : st.k * 0.9;
      st.short = shorts.length ? nearest(shorts, target).k : null;
    }
    $("c-short").innerHTML = shorts.map((o) => `<option value="${o.k}">$${fmt(o.k, o.k % 1 ? 1 : 0)} — receive $${fmt(o.m)}</option>`).join("");
    if (st.short != null) $("c-short").value = st.short;
  }
  function syncDateSlider() {
    const dte = Math.max(0, Math.round((parseDate(st.exp) - parseDate(D.today)) / DAY));
    const el = $("c-date");
    el.max = dte;
    if (st.day > dte) st.day = 0;
    el.value = st.day;
  }

  function legs() {
    const L = [];
    const lo = find(st.type, st.exp, st.k);
    if (!lo) return L;
    L.push({ type: st.type, k: st.k, iv: lo.iv > 0.05 ? lo.iv : fallbackIv(), qty: 1, paid: st.price });
    if (st.strat === "spread" && st.short != null) {
      const so = find(st.type, st.exp, st.short);
      if (so) L.push({ type: st.type, k: st.short, iv: so.iv > 0.05 ? so.iv : fallbackIv(), qty: -1, paid: so.m });
    }
    return L;
  }
  // value of the whole position per share on a given day (days from today) at price S
  function value(L, S, day) {
    const T = Math.max(0, (Math.round((parseDate(st.exp) - parseDate(D.today)) / DAY) - day)) / 365;
    const ivMult = 1 + st.ivAdj / 100;
    return L.reduce((sum, l) => sum + l.qty * bs(S, l.k, T, l.iv * ivMult, l.type, D.rate || 0.04), 0);
  }
  const cost = (L) => L.reduce((s, l) => s + l.qty * l.paid, 0); // net debit per share

  function compute() {
    const L = legs();
    if (!L.length) { $("c-stats").innerHTML = '<div class="empty">No option prices available right now.</div>'; return; }
    const q = Math.max(1, Math.min(100, parseInt($("c-qty").value, 10) || 1));
    const mult = 100 * q;
    const debit = cost(L);
    const spot = D.price;
    const dte = Math.round((parseDate(st.exp) - parseDate(D.today)) / DAY);
    const evalDate = addDays(parseDate(D.today), st.day);
    $("c-date-txt").textContent = st.day >= dte ? `${dateTxt(evalDate)} (expiration)` : st.day === 0 ? `today (${dateTxt(evalDate)})` : `${dateTxt(evalDate)} (+${st.day}d)`;
    const baseIv = L[0].iv * 100;
    $("c-iv-txt").textContent = st.ivAdj === 0 ? `none (IV ${fmt(baseIv, 0)}%)` : `${st.ivAdj > 0 ? "+" : ""}${st.ivAdj}% → IV ${fmt(baseIv * (1 + st.ivAdj / 100), 0)}%`;

    const isSpread = L.length > 1;
    const width = isSpread ? Math.abs(L[1].k - L[0].k) : null;
    const be = st.type === "c" ? L[0].k + debit : L[0].k - debit;
    const maxLoss = debit * mult;
    const maxGain = isSpread ? (width - debit) * mult : st.type === "c" ? Infinity : (L[0].k - debit) * mult;
    const plNow = (value(L, spot, st.day) - debit) * mult;
    // Typical (one standard deviation) move by expiration implied by this option's own volatility
    const emPct = dte > 0 ? L[0].iv * (1 + st.ivAdj / 100) * Math.sqrt(dte / 365) * 100 : null;
    const up = emPct ? spot * (1 + emPct / 100) : null, dn = emPct ? spot * (1 - emPct / 100) : null;
    const plUp = up ? (value(L, up, dte) - debit) * mult : null;
    const plDn = dn ? (value(L, dn, dte) - debit) * mult : null;
    const expTxt = dateTxt(parseDate(st.exp));
    const movePct = (be / spot - 1) * 100;

    const pn = (x) => (Math.round(x) >= 0 ? "pos" : "neg");
    const stat = (k, v, c = "") => `<div class="stat"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`;
    $("c-stats").innerHTML = [
      stat(isSpread ? "Net cost" : "Cost", money(maxLoss)),
      stat("Max loss", money(-maxLoss), "neg"),
      stat("Max gain", maxGain === Infinity ? "Unlimited" : money(maxGain), "pos"),
      stat("Breakeven at expiration", `$${fmt(be)} <small>(${movePct >= 0 ? "+" : ""}${fmt(movePct, 1)}%)</small>`),
      stat(st.day === 0 ? "If SPCX moved 0% today" : `If unchanged on ${dateTxt(evalDate)}`, signed(plNow), pn(plNow)),
      emPct ? stat(`Up ${fmt(emPct, 0)}% by expiration (typical move)`, signed(plUp), pn(plUp)) : "",
      emPct ? stat(`Down ${fmt(emPct, 0)}% by expiration`, signed(plDn), pn(plDn)) : "",
    ].join("");

    // table of outcomes
    const steps = [-20, -10, -5, 0, 5, 10, 20];
    const rows = steps.map((p) => {
      const S = spot * (1 + p / 100);
      const a = (value(L, S, st.day) - debit) * mult, b = (value(L, S, dte) - debit) * mult;
      const c = (x) => `<span class="${pn(x)}">${signed(x)}</span>`;
      return [`${p > 0 ? "+" : ""}${p}%`, `$${fmt(S)}`, c(a), c(b)];
    });
    const head = [["SPCX move", 0], ["Price", 1], [`P/L on ${dateTxt(evalDate)}`, 1], ["P/L at expiration", 1]];
    const tbl = $("c-table");
    tbl.innerHTML = `<thead><tr>${head.map(([h, n]) => `<th class="${n ? "n" : ""}">${h}</th>`).join("")}</tr></thead><tbody>` +
      rows.map((r) => `<tr>${r.map((x, i) => `<td class="${i ? "n" : ""}">${x}</td>`).join("")}</tr>`).join("") + "</tbody>";

    let note = `To break even by expiration, SPCX needs to be ${st.type === "c" ? "above" : "below"} $${fmt(be)}, a ${fmt(Math.abs(movePct), 1)}% move ${movePct >= 0 ? "up" : "down"}`;
    if (emPct) note += Math.abs(movePct) > emPct ? `. That's more than the ±${fmt(emPct, 0)}% typical move options are pricing in by ${expTxt}, so it needs a bigger-than-usual move.` : `. That's within the ±${fmt(emPct, 0)}% typical move options are pricing in by ${expTxt}.`;
    else note += ".";
    if (isSpread) note += ` A spread caps the gain at ${money(maxGain)} but costs less than buying the option alone.`;
    $("c-note").textContent = note;

    draw(L, debit, mult, spot, up, dn, dte);
  }

  // --- SVG chart
  function draw(L, debit, mult, spot, up, dn, dte) {
    const svg = $("c-chart");
    const W = Math.max(280, svg.getBoundingClientRect().width || svg.parentElement.clientWidth || 600), H = 260;
    const pad = { l: 58, r: 12, t: 12, b: 28 };
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const lo = spot * 0.7, hi = spot * 1.3, N = 120;
    const xs = Array.from({ length: N + 1 }, (_, i) => lo + (hi - lo) * i / N);
    const now = xs.map((S) => (value(L, S, st.day) - debit) * mult);
    const exp = xs.map((S) => (value(L, S, dte) - debit) * mult);
    let ymin = Math.min(...now, ...exp), ymax = Math.max(...now, ...exp);
    if (ymax - ymin < 1) { ymax += 1; ymin -= 1; }
    const padY = (ymax - ymin) * 0.08; ymin -= padY; ymax += padY;
    const X = (S) => pad.l + (S - lo) / (hi - lo) * (W - pad.l - pad.r);
    const Y = (v) => pad.t + (ymax - v) / (ymax - ymin) * (H - pad.t - pad.b);
    const path = (ys) => ys.map((y, i) => `${i ? "L" : "M"}${X(xs[i]).toFixed(1)},${Y(y).toFixed(1)}`).join("");
    const muted = css("--muted"), line = css("--line"), accent = css("--accent"), warnBg = css("--warn-bg"), ink = css("--ink");
    const ticksX = 6;
    let g = "";
    if (up && dn) g += `<rect x="${X(dn)}" y="${pad.t}" width="${X(up) - X(dn)}" height="${H - pad.t - pad.b}" fill="${warnBg}" />`;
    for (const v of niceTicks(ymin, ymax, 4)) {
      const y = Y(v);
      g += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${y}" y2="${y}" stroke="${line}" />`;
      g += `<text x="${pad.l - 6}" y="${y + 4}" text-anchor="end" font-size="11" fill="${muted}">${signed(v)}</text>`;
    }
    for (let i = 0; i <= ticksX; i++) {
      const S = lo + (hi - lo) * i / ticksX;
      g += `<text x="${X(S)}" y="${H - 8}" text-anchor="middle" font-size="11" fill="${muted}">$${fmt(S, 0)}</text>`;
    }
    if (ymin < 0 && ymax > 0) g += `<line x1="${pad.l}" x2="${W - pad.r}" y1="${Y(0)}" y2="${Y(0)}" stroke="${muted}" stroke-width="1.2" />`;
    g += `<line x1="${X(spot)}" x2="${X(spot)}" y1="${pad.t}" y2="${H - pad.b}" stroke="${ink}" stroke-dasharray="3 3" />`;
    g += `<text x="${X(spot) + 4}" y="${pad.t + 12}" font-size="11" fill="${ink}">now $${fmt(spot)}</text>`;
    g += `<path d="${path(exp)}" fill="none" stroke="${muted}" stroke-width="1.6" stroke-dasharray="5 4" />`;
    g += `<path d="${path(now)}" fill="none" stroke="${accent}" stroke-width="2.4" />`;
    g += `<line id="c-cross" x1="0" x2="0" y1="${pad.t}" y2="${H - pad.b}" stroke="${ink}" stroke-opacity="0" />`;
    g += `<circle id="c-dot" r="4" fill="${accent}" opacity="0" />`;
    svg.innerHTML = g;
    svg.style.height = H + "px";

    const readout = $("c-readout");
    const move = (ev) => {
      const r = svg.getBoundingClientRect();
      const cx = ((ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left) * (W / r.width);
      const S = Math.min(hi, Math.max(lo, lo + (cx - pad.l) / (W - pad.l - pad.r) * (hi - lo)));
      const a = (value(L, S, st.day) - debit) * mult, b = (value(L, S, dte) - debit) * mult;
      const cross = svg.querySelector("#c-cross"), dot = svg.querySelector("#c-dot");
      cross.setAttribute("x1", X(S)); cross.setAttribute("x2", X(S)); cross.setAttribute("stroke-opacity", "0.4");
      dot.setAttribute("cx", X(S)); dot.setAttribute("cy", Y(a)); dot.setAttribute("opacity", "1");
      readout.innerHTML = `SPCX at <b>$${fmt(S)}</b> (${S >= spot ? "+" : ""}${fmt((S / spot - 1) * 100, 1)}%): <b class="${a >= 0 ? "pos" : "neg"}">${signed(a)}</b> on the chosen date, <b class="${b >= 0 ? "pos" : "neg"}">${signed(b)}</b> at expiration`;
    };
    svg.onpointermove = move;
    svg.onpointerdown = move;
  }

  function loadContract(type, exp, k) {
    st.type = type; st.exp = exp; st.k = Number(k); st.day = 0; st.ivAdj = 0; st.strat = "single";
    setSeg("c-type", type); setSeg("c-strat", "single"); $("c-short-wrap").hidden = true;
    $("c-iv").value = 0;
    fillExp(); fillStrikes(false); syncDateSlider(); compute();
  }

  function bind() {
    document.querySelectorAll("#c-type button").forEach((b) => b.addEventListener("click", () => {
      st.type = b.dataset.v; setSeg("c-type", st.type); fillStrikes(false); compute();
    }));
    document.querySelectorAll("#c-strat button").forEach((b) => b.addEventListener("click", () => {
      st.strat = b.dataset.v; setSeg("c-strat", st.strat); $("c-short-wrap").hidden = st.strat !== "spread"; compute();
    }));
    $("c-exp").addEventListener("change", (e) => { st.exp = e.target.value; fillStrikes(false); syncDateSlider(); compute(); });
    $("c-strike").addEventListener("change", (e) => { st.k = Number(e.target.value); fillStrikes(false); compute(); });
    $("c-short").addEventListener("change", (e) => { st.short = Number(e.target.value); compute(); });
    $("c-qty").addEventListener("input", compute);
    $("c-price").addEventListener("input", (e) => { const v = parseFloat(e.target.value); if (v >= 0) { st.price = v; compute(); } });
    $("c-date").addEventListener("input", (e) => { st.day = Number(e.target.value); compute(); });
    $("c-iv").addEventListener("input", (e) => { st.ivAdj = Number(e.target.value); compute(); });
    document.addEventListener("click", (e) => {
      const b = e.target.closest("button.try");
      if (!b) return;
      loadContract(b.dataset.t, b.dataset.exp, b.dataset.k);
      $("calc-card").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    let rt;
    window.addEventListener("resize", () => { clearTimeout(rt); rt = setTimeout(() => st && compute(), 150); });
  }

  let bound = false;
  window.Calc = {
    load(type, exp, k) {
      if (!st) return;
      loadContract(type, exp, k);
      $("calc-card").scrollIntoView({ behavior: "smooth", block: "start" });
    },
    init(data) {
      D = data;
      chain = data.chain || [];
      if (!chain.length) {
        $("calc-card").querySelector(".calc-out").innerHTML = '<div class="empty">Option prices aren\'t available in this update. Check back after the next run.</div>';
        return;
      }
      if (!bound) { bind(); bound = true; }
      const first = (data.suggestions && data.suggestions.calls && data.suggestions.calls[0]) || null;
      st = { type: "c", exp: first ? first.expiry : null, k: first ? first.strike : data.price, price: 0, strat: "single", short: null, day: 0, ivAdj: 0 };
      try { compute.call(null); } catch (e) { /* fill below */ }
      loadContract("c", st.exp || chain[0].e, st.k);
    },
  };
})();
