// Token usage page (P6, TOK-07). Static: reads data/tokens.json (built by `make tokens`), no libraries.
// Every number on the page is computed from that file.
"use strict";

window.__tok = { ready: false, errors: [] };
const NS = "http://www.w3.org/2000/svg";
let D = null;

// ---------- helpers ----------
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtN = n => (n ?? 0).toLocaleString("en-US");
function fmtT(n) {  // compact token count
  if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e7 ? 1 : 2)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(n >= 1e4 ? 0 : 1)}k`;
  return String(n);
}
const pct = (v, d = 1) => `${(v * 100).toFixed(d)}%`;
const COUNTS = [["input", "Uncached input"], ["cache_creation", "Cache creation"], ["cache_read", "Cache read"], ["output", "Output"]];
function el(tag, attrs = {}, parent) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v)), f = v / p;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
}
function svgBox(container, w, h, title) {
  container.innerHTML = "";
  const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, role: "img", "aria-label": title }, container);
  return svg;
}
// tooltip shared by every chart; shown on hover and keyboard focus
function attachTip(target, html) {
  const tip = $("tip");
  const show = () => {
    tip.innerHTML = html();
    tip.hidden = false;
    const r = target.getBoundingClientRect();
    let left = window.scrollX + r.left + r.width / 2 + 10;
    if (left + tip.offsetWidth > window.scrollX + document.documentElement.clientWidth - 8) left = window.scrollX + r.left - tip.offsetWidth - 10;
    tip.style.left = `${Math.max(window.scrollX + 8, left)}px`;
    tip.style.top = `${window.scrollY + r.top}px`;
  };
  const hide = () => { tip.hidden = true; };
  target.addEventListener("mouseenter", show); target.addEventListener("focus", show);
  target.addEventListener("mouseleave", hide); target.addEventListener("blur", hide);
}
function niceTicks(max) {  // tick count that lands on round values for niceMax's 1/2/2.5/5/10 steps
  const f = max / 10 ** Math.floor(Math.log10(max));
  return f === 2 ? 4 : 5;
}
function grid(svg, m, iw, ih, max, ticks = niceTicks(max), fmt = fmtT) {
  for (let i = 0; i <= ticks; i++) {
    const v = max * i / ticks, y = m.t + ih - ih * i / ticks;
    el("line", { class: i ? "gridline" : "baseline", x1: m.l, x2: m.l + iw, y1: y, y2: y }, svg);
    el("text", { class: "tick", x: m.l - 6, y: y + 4, "text-anchor": "end" }, svg).textContent = fmt(v);
  }
}
function barPath(x, yTop, w, yBase) {  // 4px rounded data end, square at the baseline
  const r = Math.min(4, (yBase - yTop) / 2, w / 2);
  if (yBase - yTop <= 0) return "";
  return `M${x},${yBase} V${yTop + r} Q${x},${yTop} ${x + r},${yTop} H${x + w - r} Q${x + w},${yTop} ${x + w},${yTop + r} V${yBase} Z`;
}
// vertical bar chart: items [{key, label, value, tip}]
function columns(container, items, { title, h = 260, W = 640, labels = true, valueLabels = true, rotate = false } = {}) {
  const m = { t: 18, r: 8, b: labels ? (rotate ? 54 : 30) : 12, l: 48 };
  const svg = svgBox(container, W, h, title);
  const iw = W - m.l - m.r, ih = h - m.t - m.b, max = niceMax(Math.max(...items.map(i => i.value), 1));
  grid(svg, m, iw, ih, max);
  const band = iw / Math.max(items.length, 1), bw = Math.max(2, Math.min(56, band * (items.length > 20 ? 0.7 : 0.55)));
  const y = v => m.t + ih - (v / max) * ih;
  items.forEach((it, i) => {
    const cx = m.l + band * i + band / 2;
    el("path", { class: "bar", d: barPath(cx - bw / 2, y(it.value), bw, y(0)), "data-key": it.key, "data-value": it.value }, svg);
    if (valueLabels) el("text", { class: "val", x: cx, y: y(it.value) - 5, "text-anchor": "middle" }, svg).textContent = fmtT(it.value);
    if (labels) {
      const t = el("text", { class: "tick", x: cx, y: y(0) + 16, "text-anchor": rotate ? "end" : "middle",
        transform: rotate ? `rotate(-40 ${cx} ${y(0) + 12})` : "" }, svg);
      t.textContent = it.label;
    }
    const hit = el("rect", { class: "hit", x: m.l + band * i, y: m.t, width: band, height: ih, tabindex: 0,
      "aria-label": `${it.label}: ${fmtN(it.value)} tokens` }, svg);
    attachTip(hit, it.tip);
  });
  return svg;
}
function tableHTML(head, rows, caption = "") {
  return `<table>${caption ? `<caption>${esc(caption)}</caption>` : ""}<thead><tr>${head.map(([h, n]) => `<th scope="col"${n ? ' class="n"' : ""}>${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => `<tr>${r.map((c, i) => `<td${head[i][1] ? ' class="n"' : ""}>${c}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
const tallyTip = (name, t) => () => `<strong>${esc(name)}</strong><br>${fmtN(t.total)} tokens · ${fmtN(t.messages)} messages<br>` +
  COUNTS.map(([k, l]) => `<span class="fine">${l}: ${fmtN(t[k])}</span>`).join("<br>") +
  (t.cache_read_share != null ? `<br><span class="fine">Cache-read share: ${pct(t.cache_read_share)}</span>` : "");
const tallyRow = (name, t) => [esc(name), fmtN(t.total), fmtN(t.messages), ...COUNTS.map(([k]) => fmtN(t[k])),
  t.cache_read_share == null ? "—" : pct(t.cache_read_share)];
const TALLY_HEAD = [["Group"], ["Total", 1], ["Messages", 1], ...COUNTS.map(([, l]) => [l, 1]), ["Cache-read share", 1]];

// ---------- sections ----------
function renderKPIs() {
  const t = D.metrics.totals;
  const k = (id, label, value, sub) => `<div class="kpi" id="${id}"><div class="label">${esc(label)}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
  $("kpis").innerHTML =
    k("kpi-total", "Tokens processed", fmtT(t.total), `${fmtN(t.total)} across ${fmtN(t.messages)} assistant messages`) +
    k("kpi-cache", "Cache-read share", pct(t.cache_read_share), "of all input context was read from the prompt cache") +
    k("kpi-output", "Output tokens", fmtT(t.output), `${pct(t.output / t.total)} of the total`) +
    k("kpi-prompts", "Median tokens per prompt", fmtT(D.metrics.per_prompt_stats.all.median ?? 0),
      `${fmtN(D.metrics.per_prompt_stats.all.prompts)} prompts; largest ${fmtT(D.metrics.per_prompt_stats.all.max ?? 0)}`);
}
function renderGroup(key, metric, container, tableId, takeawayId, nameFn = x => x) {
  const g = D.metrics[metric];
  const entries = Object.entries(g);
  const items = entries.map(([k, t]) => ({ key: k, label: nameFn(k), value: t.total, tip: tallyTip(nameFn(k), t) }));
  columns($(container), items, { title: `Total tokens by ${key}` });
  const total = D.metrics.totals.total, top = entries.slice().sort((a, b) => b[1].total - a[1].total)[0];
  const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
  if (top) $(takeawayId).textContent = `${cap(nameFn(top[0]))} used the most: ${fmtT(top[1].total)} tokens, ${pct(top[1].total / total, 0)} of the total.`;
  $(tableId).innerHTML = tableHTML(TALLY_HEAD, entries.map(([k, t]) => tallyRow(nameFn(k), t)));
}
function renderContext() {
  const rows = D.rows.filter(r => !r.sidechain);
  const W = 960, H = 310, m = { t: 38, r: 10, b: 24, l: 52 };
  const svg = svgBox($("c-context"), W, H, "Context size per message with clear and compact boundaries");
  const iw = W - m.l - m.r, ih = H - m.t - m.b, max = niceMax(Math.max(...rows.map(r => r.context), 1));
  grid(svg, m, iw, ih, max);
  const x = i => m.l + (rows.length > 1 ? (i / (rows.length - 1)) * iw : iw / 2), y = v => m.t + ih - (v / max) * ih;
  const idxAfter = t => { const i = rows.findIndex(r => r.t > t); return i < 0 ? rows.length - 1 : i; };
  let lastX = -1e9, row = 0;
  D.boundaries.forEach(b => {
    const i = idxAfter(b.t), bx = x(i) - (rows.length > 1 ? iw / (rows.length - 1) / 2 : 0);
    row = bx - lastX < 60 ? 1 - row : 0;  // stagger labels of boundaries that sit close together
    lastX = bx;
    el("line", { class: `bound ${b.kind}`, x1: bx, x2: bx, y1: m.t - (row ? 8 : 20), y2: m.t + ih, "data-kind": b.kind }, svg);
    el("text", { class: "blabel", x: bx + 3, y: m.t - (row ? 10 : 24) }, svg).textContent = b.kind === "clear" ? "/clear" : "/compact";
  });
  el("path", { class: "ctx", d: rows.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(r.context).toFixed(1)}`).join(" ") }, svg);
  el("text", { class: "tick", x: m.l, y: H - 6 }, svg).textContent = rows.length ? rows[0].ts.slice(0, 10) : "";
  el("text", { class: "tick", x: m.l + iw, y: H - 6, "text-anchor": "end" }, svg).textContent = rows.length ? rows[rows.length - 1].ts.slice(0, 10) : "";
  // crosshair + tooltip
  const cross = el("line", { class: "cross", y1: m.t, y2: m.t + ih, visibility: "hidden" }, svg);
  const dot = el("circle", { class: "dot", r: 4, visibility: "hidden" }, svg);
  const hit = el("rect", { class: "hit", x: m.l, y: m.t, width: iw, height: ih, tabindex: 0, "aria-label": "Context size chart; use left and right arrows to read values" }, svg);
  let cur = rows.length - 1;
  const tip = $("tip");
  const place = i => {
    cur = Math.max(0, Math.min(rows.length - 1, i));
    const r = rows[cur];
    cross.setAttribute("x1", x(cur)); cross.setAttribute("x2", x(cur)); cross.setAttribute("visibility", "visible");
    dot.setAttribute("cx", x(cur)); dot.setAttribute("cy", y(r.context)); dot.setAttribute("visibility", "visible");
    tip.innerHTML = `<strong>${fmtN(r.context)} tokens of context</strong><br>${esc(r.ts.slice(0, 16).replace("T", " "))} UTC · ${esc(r.phase)} · ${esc(r.activity)}<br>
      <span class="fine">session ${esc(r.session_id)} · cache read ${fmtN(r.cache_read)}</span>`;
    tip.hidden = false;
    const sr = svg.getBoundingClientRect(), s = sr.width / W;
    let left = window.scrollX + sr.left + x(cur) * s + 12;
    if (left + tip.offsetWidth > window.scrollX + document.documentElement.clientWidth - 8) left -= tip.offsetWidth + 24;
    tip.style.left = `${left}px`; tip.style.top = `${window.scrollY + sr.top + m.t * s}px`;
  };
  const hide = () => { tip.hidden = true; cross.setAttribute("visibility", "hidden"); dot.setAttribute("visibility", "hidden"); };
  hit.addEventListener("mousemove", e => {
    const sr = svg.getBoundingClientRect(), px = (e.clientX - sr.left) * (W / sr.width);
    place(Math.round(((px - m.l) / iw) * (rows.length - 1)));
  });
  hit.addEventListener("mouseleave", hide); hit.addEventListener("blur", hide);
  hit.addEventListener("focus", () => place(cur));
  hit.addEventListener("keydown", e => {
    const d = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
    if (d) { e.preventDefault(); place(cur + d); }
  });
  const clearIco = '<svg width="22" height="10" aria-hidden="true"><line x1="0" y1="5" x2="22" y2="5" stroke="currentColor" stroke-width="1.5" stroke-dasharray="5 4"/></svg>';
  const compIco = '<svg width="22" height="10" aria-hidden="true"><line x1="1" y1="5" x2="21" y2="5" stroke="currentColor" stroke-width="1.5" stroke-dasharray="1 3" stroke-linecap="round"/></svg>';
  const n = k => D.boundaries.filter(b => b.kind === k).length;
  $("l-context").innerHTML = `<span>${clearIco}/clear (${n("clear")})</span><span>${compIco}/compact (${n("compact")})</span>`;
  const drops = D.metrics.boundary_drops.filter(d => d.context_before != null && d.context_after != null);
  const big = drops.slice().sort((a, b) => (b.context_before - b.context_after) - (a.context_before - a.context_after))[0];
  $("t-context").textContent = big
    ? `Context grows within a session and falls at each boundary: the largest drop was ${fmtT(big.context_before)} → ${fmtT(big.context_after)} at a ${big.kind === "clear" ? "/clear" : "/compact"}.`
    : "No clear or compact boundaries have been logged yet.";
  $("tbl-context").innerHTML = tableHTML([["When"], ["Boundary"], ["Context before", 1], ["Context after", 1]],
    D.metrics.boundary_drops.map(d => [esc(d.ts.slice(0, 16).replace("T", " ")), d.kind === "clear" ? "/clear" : "/compact",
      d.context_before == null ? "—" : fmtN(d.context_before), d.context_after == null ? "—" : fmtN(d.context_after)]));
}
function renderPrompts() {
  const pp = D.metrics.per_prompt;
  const items = pp.map((p, i) => ({ key: String(p.event_line), label: String(i + 1), value: p.total,
    tip: () => `<strong>Prompt ${i + 1}</strong> · ${esc(p.phase)} · ${esc(p.activity)}<br>${esc(p.ts.slice(0, 16).replace("T", " "))}<br>${fmtN(p.total)} tokens in ${fmtN(p.messages)} messages` }));
  columns($("c-prompt"), items, { title: "Tokens per prompt, in time order", h: 260, W: 960, labels: false, valueLabels: false });
  const s = D.metrics.per_prompt_stats.all, zero = pp.filter(p => p.messages === 0).length;
  $("t-prompt").textContent = `A typical prompt cost ${fmtT(s.median ?? 0)} tokens (median), but a few long ones dominate: the largest used ${fmtT(s.max ?? 0)}.` +
    (zero ? ` ${zero} prompts (shell commands) used none.` : "");
  $("tbl-prompt").innerHTML = tableHTML([["#"], ["When"], ["Phase"], ["Activity"], ["Messages", 1], ["Total", 1]],
    pp.map((p, i) => [String(i + 1), esc(p.ts.slice(0, 16).replace("T", " ")), esc(p.phase), esc(p.activity), fmtN(p.messages), fmtN(p.total)]));
}
const STATUS = { measured: ["measured", "Measured"], "awaiting transcript": ["awaiting", "Run logged; transcript not copied yet"], "not run": ["notrun", "Not run yet"] };
function renderExperiment() {
  const e = D.experiment;
  $("exp-caveat").innerHTML = `<strong>Small sample:</strong> ${esc(e.caveat)}`;
  const rows = Object.entries(e.conditions).map(([c, v]) => {
    const [cls, label] = STATUS[v.status] || ["notrun", v.status];
    return `<tr data-cond="${c}" data-status="${esc(v.status)}"><th scope="row">${c}</th><td class="wrap">${esc(v.label)}</td>
      <td><span class="status ${cls}">${esc(label)}</span></td><td class="n">${fmtN(v.runs)}</td><td class="n">${fmtN(v.messages)}</td>
      <td class="n">${v.messages ? fmtN(v.total) : "—"}</td><td class="n">${v.first_context == null ? "—" : fmtN(v.first_context)}</td>
      <td class="n">${v.peak_context == null ? "—" : fmtN(v.peak_context)}</td><td class="n">${v.messages ? fmtN(v.output) : "—"}</td></tr>`;
  }).join("");
  $("exp-table").innerHTML = `<thead><tr><th scope="col">Run</th><th scope="col">Condition</th><th scope="col">Status</th><th scope="col" class="n">Runs</th>
    <th scope="col" class="n">Messages</th><th scope="col" class="n">Total tokens</th><th scope="col" class="n">Starting context</th>
    <th scope="col" class="n">Peak context</th><th scope="col" class="n">Output</th></tr></thead><tbody>${rows}</tbody>`;
  const measured = Object.entries(e.conditions).filter(([, v]) => v.messages);
  if (measured.length) {
    columns($("c-exp"), measured.map(([c, v]) => ({ key: c, label: `${c}: ${v.label}`, value: v.total, tip: tallyTip(`Run ${c}`, v) })),
      { title: "Total tokens per experiment run", h: 220 });
  } else {
    $("c-exp").innerHTML = `<p class="empty">No run has been measured yet, so there is nothing to compare.</p>`;
  }
  $("exp-excluded").innerHTML = e.excluded.length
    ? `<p class="panel-note">Excluded (sent without following the protocol): ${e.excluded.map(x =>
        `run ${esc(x.condition)} at ${esc(x.ts.slice(11, 16))} (logs/events.jsonl line ${x.event_line}): ${esc(x.reason)}`).join("; ")}.</p>` : "";
}
function renderLimits() {
  const L = D.usage_limits;
  $("limits").innerHTML = L.length
    ? `<div class="table-wrap">${tableHTML([["When"], ["Plan"], ["What happened"], ["Phase"], ["Notes"]],
        L.map(r => [esc(r.when), esc(r.plan), `<span class="wrap">${esc(r.what)}</span>`, esc(r.phase), esc(r.notes)]))}</div>`
    : `<p class="empty" id="limits-empty">No usage-limit events logged yet.</p>`;
}
function renderLearned() {
  $("learned").innerHTML = D.learned
    ? D.learned.trim().split(/\n\s*\n/).map(b => { const h = b.match(/^#{1,6}\s+(.*)$/); return h && !b.includes("\n") ? `<h3>${esc(h[1])}</h3>` : `<p>${esc(b)}</p>`; }).join("")
    : `<p class="empty" id="learned-missing">Not written yet. Aayush will add it in <code>docs/tokens-learned.md</code>.</p>`;
}
function setupToggles() {
  document.querySelectorAll(".tbl-toggle").forEach(btn => {
    const target = $(btn.getAttribute("aria-controls")), show = btn.textContent;
    btn.addEventListener("click", () => {
      const open = target.hidden;
      target.hidden = !open;
      btn.setAttribute("aria-expanded", String(open));
      btn.textContent = open ? show.replace(/^Show/, "Hide") : show;
    });
  });
}
function setupTheme() {
  const btn = $("theme-toggle");
  const label = () => {
    const t = document.documentElement.dataset.theme || "auto";
    btn.textContent = `Theme: ${t}`;
    btn.setAttribute("aria-label", `Color theme: ${t === "auto" ? "follow system" : t}. Activate to change.`);
  };
  btn.addEventListener("click", () => {
    const order = ["auto", "light", "dark"], cur = document.documentElement.dataset.theme || "auto";
    const next = order[(order.indexOf(cur) + 1) % order.length];
    if (next === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = next;
    try { if (next === "auto") localStorage.removeItem("dash-theme"); else localStorage.setItem("dash-theme", next); } catch (e) {}
    label();
  });
  label();
}
function fail(e) {
  window.__tok.errors.push(String(e));
  const el2 = $("load-error");
  el2.hidden = false;
  el2.textContent = `Could not build the page: ${e.message || e}. Serve the site/ folder over HTTP (make serve) so the data file can load.`;
  console.error(e);
}
async function main() {
  try {
    const r = await fetch("data/tokens.json");
    if (!r.ok) throw new Error(`tokens.json: HTTP ${r.status}`);
    D = await r.json();
    if (!Array.isArray(D.rows) || !D.metrics) throw new Error("tokens.json is missing rows or metrics");
    const s = D.sources;
    $("run-line").textContent = `${fmtN(D.rows.length)} assistant messages from ${s.transcripts} session transcripts and ${s.subagent_transcripts} subagent transcripts. ${s.not_covered}`;
    renderKPIs();
    renderGroup("phase", "by_phase", "c-phase", "tbl-phase", "t-phase");
    renderGroup("activity", "by_activity", "c-activity", "tbl-activity", "t-activity");
    $("n-activity").textContent = `Activity is the part of .phase after the colon. Logged so far: ${D.metrics.activities_logged.join(", ")}.`;
    renderContext(); renderPrompts(); renderExperiment(); renderLimits(); renderLearned();
    setupToggles(); setupTheme();
    window.__tok.ready = true;
  } catch (e) { fail(e); }
}
main();
