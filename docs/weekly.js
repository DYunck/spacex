(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (x, d = 2) => Number(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 1) => (x == null ? "—" : (x > 0 ? "+" : "") + fmt(x, d) + "%");
  const cls = (x) => (x > 0 ? "pos" : x < 0 ? "neg" : "muted");
  const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const day = (iso, opts) => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d).toLocaleDateString(undefined, opts); };

  function bars(weeks) {
    const svg = $("bars");
    const W = Math.max(280, svg.getBoundingClientRect().width || 600), H = 170, pad = { l: 8, r: 8, t: 18, b: 30 };
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    const ws = weeks.slice().reverse();
    const maxAbs = Math.max(2, ...ws.map((w) => Math.abs(w.change_pct || 0)));
    const zero = pad.t + (H - pad.t - pad.b) / 2, half = (H - pad.t - pad.b) / 2;
    const bw = (W - pad.l - pad.r) / ws.length;
    let g = `<line x1="${pad.l}" x2="${W - pad.r}" y1="${zero}" y2="${zero}" stroke="${css("--line")}" />`;
    const every = bw < 34 ? 3 : bw < 50 ? 2 : 1;
    ws.forEach((w, i) => {
      const v = w.change_pct || 0, h = Math.abs(v) / maxAbs * half, x = pad.l + i * bw + bw * 0.18, wdt = bw * 0.64;
      const y = v >= 0 ? zero - h : zero;
      const col = v >= 0 ? css("--up") : css("--down");
      g += `<rect x="${x}" y="${y}" width="${wdt}" height="${Math.max(1, h)}" rx="3" fill="${col}" opacity="${w.in_progress ? 0.45 : 0.9}"><title>Week of ${w.week_of}: ${pct(v)}</title></rect>`;
      const showLabel = (ws.length - 1 - i) % every === 0;
      if (showLabel) g += `<text x="${x + wdt / 2}" y="${H - 8}" text-anchor="middle" font-size="10.5" fill="${css("--muted")}">${day(w.week_of, { month: "short", day: "numeric" })}</text>`;
      if (bw >= 26) g += `<text x="${x + wdt / 2}" y="${v >= 0 ? Math.max(11, y - 4) : Math.min(H - pad.b + 10, y + h + 11)}" text-anchor="middle" font-size="10" fill="${col}">${(v > 0 ? "+" : "") + v.toFixed(1)}</text>`;
    });
    svg.innerHTML = g;
  }

  function render(data) {
    const weeks = data.weeks || [];
    $("lede").textContent = `One card per trading week, newest first. Updated ${new Date(data.generated).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}.`;
    if (String(data.source).includes("SAMPLE")) $("banners").innerHTML = '<div class="banner warn">These are SAMPLE numbers for testing, not real market data.</div>';
    bars(weeks.slice(0, 12));
    window.addEventListener("resize", () => bars(weeks.slice(0, 12)));
    $("weeks").innerHTML = weeks.map((w) => {
      const stat = (k, v, c = "") => `<div class="stat"><div class="k">${k}</div><div class="v ${c}">${v}</div></div>`;
      const evs = w.events.length ? `<div class="wk-sub">Events</div><ul class="wk-list">${w.events.map((e) =>
        `<li><span class="muted">${day(e.date, { weekday: "short", month: "short", day: "numeric" })}</span><span>${esc(e.title)}</span></li>`).join("")}</ul>` : "";
      const sigs = w.signals.length ? `<div class="wk-sub">Strong signals</div><ul class="wk-list">${w.signals.map((s) =>
        `<li><span class="muted">${new Date(s.time).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}</span><span>${esc(s.label)} (${s.score > 0 ? "+" : ""}${s.score}) at $${fmt(s.price)}</span>` +
        `<span>${s.after_5d == null ? '<span class="muted">result after 5 days pending</span>' : `5 days later: <b class="${s.right_5d ? "pos" : "neg"}">${pct(s.after_5d)}</b> (${s.right_5d ? "right" : "wrong"})`}</span></li>`).join("")}</ul>` : "";
      const best = w.best_day ? `${day(w.best_day.date, { weekday: "short" })} ${pct(w.best_day.pct)}` : "—";
      const worst = w.worst_day ? `${day(w.worst_day.date, { weekday: "short" })} ${pct(w.worst_day.pct)}` : "—";
      return `<section class="card wk">
        <div class="wk-head"><h2>Week of ${day(w.week_of, { month: "long", day: "numeric" })}</h2>
          <span class="wk-chg ${cls(w.change_pct)}">${pct(w.change_pct)}</span>
          ${w.in_progress ? '<span class="chip warn">In progress</span>' : ""}</div>
        <p class="wk-recap">${esc(w.recap)}</p>
        <div class="wk-stats">
          ${stat("Open → close", `$${fmt(w.open)} → $${fmt(w.close)}`)}
          ${stat("Low – high", `$${fmt(w.low)} – $${fmt(w.high)}`)}
          ${stat("Best day", best, w.best_day && w.best_day.pct > 0 ? "pos" : "")}
          ${stat("Worst day", worst, w.worst_day && w.worst_day.pct < 0 ? "neg" : "")}
          ${stat("Volume vs. usual", w.volume_vs_prior ? fmt(w.volume_vs_prior, 1) + "×" : "—")}
          ${stat("Daily-chart score", `${w.score_end > 0 ? "+" : ""}${w.score_end}`, w.score_end >= 20 ? "pos" : w.score_end <= -20 ? "neg" : "")}
        </div>${evs}${sigs}</section>`;
    }).join("") || '<div class="empty">No weeks to show yet.</div>';
  }

  fetch("data/weekly.json?ts=" + Date.now()).then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(render).catch((e) => { $("lede").textContent = "No weekly data yet."; $("banners").innerHTML = `<div class="banner warn">Couldn't load the weekly recap (${esc(e.message)}). It appears after the next scheduled update.</div>`; });
})();
