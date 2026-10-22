// Starship flight tracker, insider-selling (lockup) tracker and analyst price targets.
(function () {
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (x, d = 2) => Number(x).toLocaleString(undefined, { minimumFractionDigits: d, maximumFractionDigits: d });
  const pct = (x, d = 1) => (x == null ? "—" : (x > 0 ? "+" : "") + fmt(x, d) + "%");
  const cls = (x) => (x > 0 ? "pos" : x < 0 ? "neg" : "muted");
  const money = (x, d = 2) => (x == null ? "—" : "$" + fmt(x, d));
  const shares = (m) => (m == null ? "—" : m >= 1000 ? fmt(m / 1000, 2) + "B" : fmt(m, m < 100 ? 1 : 0) + "M");
  const dateTxt = (s, opts = { month: "short", day: "numeric", year: "numeric" }) => {
    if (!s) return "—";
    const [y, m, d] = s.slice(0, 10).split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString(undefined, opts);
  };
  function table(el, head, rows, empty) {
    if (!el) return;
    if (!rows.length) { el.outerHTML = `<div class="empty" id="${el.id}">${empty}</div>`; return; }
    if (el.tagName !== "TABLE") { const t = document.createElement("table"); t.id = el.id; el.replaceWith(t); el = t; }
    el.innerHTML = `<thead><tr>${head.map(([h, n]) => `<th class="${n ? "n" : ""}">${h}</th>`).join("")}</tr></thead>` +
      `<tbody>${rows.map((r) => `<tr>${r.map((c, i) => `<td class="${head[i][1] ? "n" : ""}">${c}</td>`).join("")}</tr>`).join("")}</tbody>`;
  }

  // ------------------------------------------------------------ Starship
  function renderStarship(d) {
    const s = d.starship;
    if (!s || !s.flights || !s.flights.length) {
      $("ss-summary").innerHTML = "";
      table($("ss-table"), [], [], "Starship flight history isn't available right now. It's refreshed every hour.");
      return;
    }
    const su = s.summary;
    const chip = (t, c = "") => `<span class="chip ${c}">${t}</span>`;
    const chips = [chip(`${su.since_ipo} flight${su.since_ipo === 1 ? "" : "s"} since the IPO`),
      chip(`${su.successes} success${su.successes === 1 ? "" : "es"}`, "up")];
    if (su.failures) chips.push(chip(`${su.failures} failure${su.failures === 1 ? "" : "s"}`, "down"));
    if (su.avg_move_success != null) chips.push(chip(`After successes: SPCX ${pct(su.avg_move_success)} on average`, su.avg_move_success >= 0 ? "up" : "down"));
    if (su.avg_move_failure != null) chips.push(chip(`After failures: ${pct(su.avg_move_failure)} on average`, su.avg_move_failure >= 0 ? "up" : "down"));
    $("ss-summary").innerHTML = chips.join("");
    const n = s.next;
    $("ss-next").innerHTML = n ? `<div class="callout-row">🚀 <b>Next Starship flight:</b> ${esc(n.name)}, ${n.net ? new Date(n.net).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : "date TBD"}${n.status && n.status !== "Go" ? ` <span class="muted">(${esc(n.status)}, dates often slip)</span>` : ""}</div>` : "";
    const resCls = { Success: "up", Failure: "down", "Partial failure": "warn" };
    table($("ss-table"), [["Date", 0], ["Flight", 0], ["Result", 0], ["Reaction", 1], ["2-day", 1], ["Details", 0]],
      s.flights.map((f) => {
        const r = f.reaction;
        const detail = f.failreason || f.description;
        return [dateTxt(f.date), esc(f.name), `<span class="chip ${resCls[f.result] || ""}">${esc(f.result)}</span>`,
          f.before_ipo ? '<span class="muted">before IPO</span>' : r ? `<span class="${cls(r.move_pct)}">${pct(r.move_pct)}</span>` : '<span class="muted">next session</span>',
          f.before_ipo || !r || r.move_2d_pct == null ? "—" : `<span class="${cls(r.move_2d_pct)}">${pct(r.move_2d_pct)}</span>`,
          detail ? `<span class="ss-detail">${esc(detail)}</span>` : ""];
      }), "No Starship flights found.");
  }

  // ------------------------------------------------------------ lockups
  function renderLockups(d) {
    const L = d.lockups;
    if (!L) return;
    const total = L.total_m;
    const segs = [
      ["Freely tradable", L.tradable_m, "var(--up)"],
      ["Unlocking by Dec 8", L.upcoming_standard_m, "var(--warn)"],
      ["Musk & other insiders (2027)", L.extended_m, "var(--muted)"],
    ];
    if (L.other_locked_m > total * 0.005) segs.push(["Other / unaccounted", L.other_locked_m, "var(--line)"]);
    $("lk-bar").innerHTML = segs.map(([name, v, c]) => `<div style="flex:${Math.max(v, 0)};background:${c}" title="${esc(name)}: ${shares(v)}"><span>${v / total >= 0.08 ? Math.round(v / total * 100) + "%" : ""}</span></div>`).join("");
    $("lk-legend").innerHTML = segs.map(([name, v, c]) => `<span><i style="background:${c};height:10px"></i>${esc(name)}: <b>${shares(v)}</b> (${fmt(v / total * 100, 0)}%)</span>`).join("");
    const nx = L.next;
    $("lk-next").innerHTML = nx ? `<div class="lk-next"><div class="lk-count">${nx.days === 0 ? "Today" : nx.days === 1 ? "Tomorrow" : `In ${nx.days} days`}</div>
      <div><b>Next unlock: ${dateTxt(nx.date, { weekday: "short", month: "short", day: "numeric" })}</b> — about <b>${shares(nx.shares_m)}</b> shares (${fmt(nx.pct_of_company, 1)}% of the company) become eligible for sale.<br>
      <span class="muted">${esc(nx.note)}. Freely tradable shares would go from ${shares(L.tradable_m)} to ${shares(L.tradable_m + (nx.shares_m || 0))} (${pct((nx.shares_m || 0) / L.tradable_m * 100, 0).replace("+", "+")}).</span></div></div>` : "";
    const chips = [`<span class="chip">Tradable now: ${shares(L.tradable_m)} of ${shares(total)} (${fmt(L.tradable_pct, 0)}%)</span>`,
      `<span class="chip warn">After Dec 8: about ${fmt(L.after_dec8_pct, 0)}% tradable</span>`];
    if (L.past_unlocks) chips.push(`<span class="chip ${L.past_avg_move >= 0 ? "up" : "down"}">Past unlock days: up ${L.past_up} of ${L.past_unlocks}, average ${pct(L.past_avg_move)}</span>`);
    if (L.yahoo_float_m || L.yahoo_outstanding_m) chips.push(`<span class="chip dim">Yahoo reports ${L.yahoo_float_m ? shares(L.yahoo_float_m) + " float" : ""}${L.yahoo_float_m && L.yahoo_outstanding_m ? " / " : ""}${L.yahoo_outstanding_m ? shares(L.yahoo_outstanding_m) + " outstanding" : ""} (likely one share class)</span>`);
    $("lk-chips").innerHTML = chips.join("");
    table($("lk-table"), [["Date", 0], ["Shares", 1], ["% of company", 1], ["Who", 0], ["Status", 0], ["Move", 1], ["Notes", 0]],
      L.rows.map((r) => [
        r.date ? dateTxt(r.date) : esc(r.label || "TBD"),
        shares(r.shares_m), r.pct_of_company == null ? "—" : fmt(r.pct_of_company, 1) + "%",
        r.group === "extended" ? "Musk & insiders" : "Employees & early investors",
        r.status === "released" ? '<span class="chip dim">Released</span>' : r.status === "upcoming" ? `<span class="chip warn">${r.days === 0 ? "Today" : `In ${r.days}d`}</span>` : '<span class="chip dim">Date TBD</span>',
        r.move_pct == null ? "—" : `<span class="${cls(r.move_pct)}">${pct(r.move_pct)}</span>`,
        `<span class="ss-detail">${esc(r.note)}</span>`]), "No unlock schedule.");
  }

  // ------------------------------------------------------------ analysts
  function renderAnalysts(d) {
    const A = d.analysts;
    if (!A) {
      $("an-head").innerHTML = '<div class="empty">Analyst data isn\'t available from Yahoo right now. It\'s retried every hour.</div>';
      $("an-range").innerHTML = ""; $("an-mix").innerHTML = "";
      table($("an-changes"), [], [], "No recent rating changes.");
      return;
    }
    const t = A.targets || {}, p = A.price;
    const head = [];
    if (t.mean) head.push(`<div class="an-big"><span class="muted">Average target</span><b>${money(t.mean)}</b><span class="${cls(A.upside_mean_pct)}">${pct(A.upside_mean_pct)} from today</span></div>`);
    if (A.rating_text) head.push(`<div class="an-big"><span class="muted">Consensus <button class="ex" data-ex="rating" aria-label="Explain">i</button></span><b>${esc(A.rating_text)}</b><span class="muted">${A.rating_mean ? fmt(A.rating_mean, 1) + " on a 1–5 scale" : ""}</span></div>`);
    if (A.count) head.push(`<div class="an-big"><span class="muted">Analysts</span><b>${A.count}</b><span class="muted">covering SPCX</span></div>`);
    $("an-head").innerHTML = `<div class="an-heads">${head.join("")}</div>`;

    if (t.low && t.high && t.high > t.low) {
      const lo = Math.min(t.low, p) * 0.95, hi = Math.max(t.high, p) * 1.03;
      const X = (v) => ((v - lo) / (hi - lo) * 100).toFixed(2) + "%";
      const mk = (v, label, c) => v ? `<div class="an-mark ${c}" style="left:${X(v)}"><i></i><span>${label}<br><b>${money(v, 0)}</b></span></div>` : "";
      $("an-range").innerHTML = `<div class="an-track"><div class="an-fill" style="left:${X(t.low)};width:calc(${X(t.high)} - ${X(t.low)})"></div>
        ${mk(t.low, "Low", "lo")}${mk(t.mean, "Average", "mid")}${mk(t.high, "High", "hi")}
        <div class="an-now" style="left:${X(p)}"><span>Today ${money(p, 0)}</span></div></div>`;
    } else $("an-range").innerHTML = "";

    const mix = A.mix;
    if (mix) {
      const parts = [["Strong buy", mix.strongBuy, "var(--up)"], ["Buy", mix.buy, "color-mix(in srgb, var(--up) 55%, var(--card))"],
        ["Hold", mix.hold, "var(--line)"], ["Sell", mix.sell, "color-mix(in srgb, var(--down) 55%, var(--card))"], ["Strong sell", mix.strongSell, "var(--down)"]];
      const tot = parts.reduce((a, x) => a + (x[1] || 0), 0);
      $("an-mix").innerHTML = tot ? `<h3 class="sub">Ratings this month</h3><div class="an-mixbar">${parts.filter((x) => x[1]).map(([n, v, c]) => `<div style="flex:${v};background:${c}" title="${n}: ${v}"><span>${v}</span></div>`).join("")}</div>
        <div class="legend">${parts.map(([n, v, c]) => `<span><i style="background:${c};height:10px"></i>${n}: ${v || 0}</span>`).join("")}</div>` : "";
    } else $("an-mix").innerHTML = "";

    const act = { up: "Upgrade", down: "Downgrade", main: "Maintained", init: "New coverage", reit: "Reiterated" };
    table($("an-changes"), [["Date", 0], ["Firm", 0], ["Rating", 0], ["Target", 1]],
      (A.changes || []).slice(0, 8).map((c) => [dateTxt(c.date, { month: "short", day: "numeric" }), esc(c.firm),
        `${esc(c.to || "—")}${c.action && act[c.action] ? ` <span class="chip ${c.action === "up" ? "up" : c.action === "down" ? "down" : "dim"}">${act[c.action]}</span>` : ""}`,
        c.target ? `${money(c.target, 0)}${c.prior_target && c.prior_target !== c.target ? ` <span class="${cls(c.target - c.prior_target)}">(${c.target > c.prior_target ? "↑" : "↓"} from ${money(c.prior_target, 0)})</span>` : ""}` : "—"]),
      "No recent rating changes.");
  }

  window.Trackers = {
    init(d) {
      for (const f of [renderStarship, renderLockups, renderAnalysts]) {
        try { f(d); } catch (e) { console.error(e); }
      }
    },
  };
})();
