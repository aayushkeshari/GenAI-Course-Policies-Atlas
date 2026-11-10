// Contribution timeline (P5). Static: reads data/timeline.json (built by `make timeline`), no build step, no libraries.
// Every count on the page is computed from that file; nothing is typed in by hand.
"use strict";

window.__tl = { ready: false, errors: [] };
const DATA_URL = "data/timeline.json";
let D = null;
let BY_ID = {};

const ACTOR_LABEL = { HUMAN: "Aayush (human)", CLAUDE: "Claude", shared: "shared / unclear" };
const ACTOR_SHORT = { HUMAN: "HUMAN", CLAUDE: "CLAUDE", shared: "shared" };
const TYPE_LABEL = { prompt: "prompt", response: "response", session: "session", commit: "commit",
  spec_edit: "spec edit", progress: "progress log", review: "review log" };
const ZOOMS = [  // px per hour of real time between consecutive items; 0 = order only
  [0, "Order only"], [15, "15 px per hour"], [60, "1 px per minute"], [240, "4 px per minute"], [960, "16 px per minute"]];
const GAP_CAP_H = 4;          // gaps longer than this are shortened and labelled
const ORDER_GAP_LABEL_H = 1;  // in "order only", label gaps over an hour

// ---------- helpers ----------
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtN = n => n.toLocaleString("en-US");
function dur(ms) {
  const m = Math.round(ms / 60000);
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60), r = m % 60;
  if (h < 48) return r ? `${h} h ${r} min` : `${h} h`;
  return `${Math.round(h / 24)} days`;
}
const marker = a => `<span class="mk ${esc(a)}" aria-hidden="true"></span>`;
function hashParams() { return new URLSearchParams(location.hash.replace(/^#/, "")); }
function setHash(updates, replace = false) {
  const h = hashParams();
  for (const [k, v] of Object.entries(updates)) {
    if (v === undefined || v === null || v === "") h.delete(k); else h.set(k, v);
  }
  const next = h.toString();
  if (location.hash.replace(/^#/, "") === next) { route(); return; }
  if (replace) { history.replaceState(null, "", "#" + next); route(); } else location.hash = next;
}
function options(sel, values, labelFn, allLabel) {
  sel.innerHTML = `<option value="">${esc(allLabel)}</option>` +
    values.map(v => `<option value="${esc(v)}">${esc(labelFn(v))}</option>`).join("");
}
function highlight(text, q) {
  const t = esc(text);
  if (!q) return t;
  const re = new RegExp(esc(q).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  return t.replace(re, m => `<mark>${m}</mark>`);
}

// ---------- timeline view ----------
function tlFilters(p) {
  return { actor: p.get("actor") || "", phase: p.get("phase") || "", type: p.get("type") || "", cat: p.get("cat") || "" };
}
function tlMatch(it, f) {
  return (!f.actor || it.actor === f.actor) && (!f.phase || it.phase === f.phase) && (!f.type || it.type === f.type)
    && (!f.cat || (it.type === "prompt" && it.category === f.cat));
}
function zoomIndex(p) {
  const z = parseInt(p.get("zoom") ?? "0", 10);
  return Number.isFinite(z) ? Math.max(0, Math.min(ZOOMS.length - 1, z)) : 0;
}
function detailHTML(it) {
  const rows = [["Who", `${ACTOR_LABEL[it.actor]}`], ["What", TYPE_LABEL[it.type]],
    ["Phase", it.phase + (it.stage ? ` (${it.stage})` : "")], ["When", it.ts + (it.ts_precision === "day" ? " (date only)" : "")],
    ["Source", `<code>${esc(it.source)}</code>`]];
  if (it.category) rows.push(["Prompt category", esc(it.category)]);
  if (it.session) rows.push(["Session", `<code>${esc(it.session)}</code>`]);
  if (it.type === "commit" || it.type === "spec_edit") rows.push(["Lines", `+${it.added} / −${it.removed}`]);
  let html = `<dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${k === "Source" || k === "Session" || k === "Lines" ? v : esc(v)}</dd>`).join("")}</dl>`;
  if (it.text) html += `<pre class="txt">${esc(it.text)}</pre>`;
  const pair = it.type === "prompt" ? it.id : it.reply_to;
  if (pair) html += `<p><a href="#${esc(new URLSearchParams({ view: "qa", focus: pair }).toString())}">Open this exchange in Prompts &amp; responses</a></p>`;
  return html;
}
function renderTimeline(p) {
  const f = tlFilters(p);
  for (const [id, k] of [["f-actor", "actor"], ["f-phase", "phase"], ["f-type", "type"], ["f-cat", "cat"]]) $(id).value = f[k];
  const zi = zoomIndex(p), [pxh, zlabel] = ZOOMS[zi];
  $("zoom-label").textContent = zlabel;
  $("zoom-out").disabled = zi === 0;
  $("zoom-in").disabled = zi === ZOOMS.length - 1;
  const mode = p.get("mode") === "clear" ? "clear" : "compact";
  $("mode-compact").setAttribute("aria-pressed", String(mode === "compact"));
  $("mode-clear").setAttribute("aria-pressed", String(mode === "clear"));
  const list = $("tl-list");
  list.classList.toggle("clear", mode === "clear");
  list.dataset.zoom = String(pxh);

  const shown = D.items.filter(it => tlMatch(it, f));
  $("tl-count").textContent = `${fmtN(shown.length)} of ${fmtN(D.items.length)} items`;
  const open = new Set((p.get("open") || "").split(",").filter(Boolean));
  const out = [];
  let prev = null, prevDay = null;
  for (const it of shown) {
    const day = it.ts.slice(0, 10);
    let space = 0;
    if (prev) {
      const dt = it.t - prev.t, capped = dt > GAP_CAP_H * 3600e3;
      if (capped || (pxh === 0 && dt > ORDER_GAP_LABEL_H * 3600e3)) {
        out.push(`<li class="gap" data-gap-ms="${dt}">… ${esc(dur(dt))} later${capped && pxh ? " (gap shortened)" : ""} …</li>`);
      }
      space = pxh ? Math.round(Math.min(dt, GAP_CAP_H * 3600e3) / 3600e3 * pxh) : 0;
    }
    if (day !== prevDay) { out.push(`<li class="day">${esc(day)}</li>`); space = 0; }
    const isOpen = open.has(it.id);
    out.push(`<li class="row item" data-id="${esc(it.id)}" data-actor="${esc(it.actor)}" data-type="${esc(it.type)}" data-phase="${esc(it.phase)}" style="margin-top:${space}px">
      <span class="time">${esc(it.ts_precision === "day" ? "—" : it.ts.slice(11, 16))}</span>
      <span class="dot">${marker(it.actor)}</span>
      <div class="body">
        <button class="head" type="button" aria-expanded="${isOpen}" aria-controls="d-${esc(it.id)}">
          <span class="sr">${esc(ACTOR_LABEL[it.actor])}:</span>
          <span class="who ${esc(it.actor)}" aria-hidden="true">${esc(ACTOR_SHORT[it.actor])}</span>
          <span class="tchip">${esc(TYPE_LABEL[it.type])}</span>
          <span class="tchip ph">${esc(it.phase)}</span>
          <span class="sum">${esc(it.summary)}</span>
        </button>
        ${it.text ? `<div class="preview">${esc(it.text.slice(0, 400))}</div>` : ""}
        <div class="detail" id="d-${esc(it.id)}" ${isOpen ? "" : "hidden"}>${isOpen ? detailHTML(it) : ""}</div>
      </div></li>`);
    prev = it; prevDay = day;
  }
  list.innerHTML = out.join("") || `<li class="gap">No items match these filters.</li>`;
}
function setupTimeline() {
  options($("f-actor"), D.actors, a => ACTOR_LABEL[a], "All actors");
  options($("f-phase"), D.phases, v => v, "All phases");
  options($("f-type"), D.types, t => TYPE_LABEL[t], "All types");
  options($("f-cat"), D.categories, c => c, "Any (all items)");
  for (const [id, k] of [["f-actor", "actor"], ["f-phase", "phase"], ["f-type", "type"], ["f-cat", "cat"]]) {
    $(id).addEventListener("change", e => setHash({ [k]: e.target.value }));
  }
  const zoomBy = d => setHash({ zoom: String(Math.max(0, Math.min(ZOOMS.length - 1, zoomIndex(hashParams()) + d))) || null }, true);
  $("zoom-in").addEventListener("click", () => zoomBy(1));
  $("zoom-out").addEventListener("click", () => zoomBy(-1));
  $("tl-list").addEventListener("wheel", e => {
    if (!(e.ctrlKey || e.metaKey)) return;
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 1 : -1);
  }, { passive: false });
  $("mode-compact").addEventListener("click", () => setHash({ mode: null }, true));
  $("mode-clear").addEventListener("click", () => setHash({ mode: "clear" }, true));
  $("tl-list").addEventListener("click", e => {
    const btn = e.target.closest("button.head");
    if (!btn) return;
    const li = btn.closest("li.item"), id = li.dataset.id, det = $(`d-${id}`);
    const nowOpen = det.hidden;
    det.hidden = !nowOpen;
    btn.setAttribute("aria-expanded", String(nowOpen));
    if (nowOpen && !det.innerHTML) det.innerHTML = detailHTML(BY_ID[id]);
  });
  $("tl-legend").innerHTML = D.actors.map(a => `<span>${marker(a)}${esc(ACTOR_LABEL[a])}</span>`).join("") +
    `<span>Click an item for details and its source.</span>`;
}

// ---------- Q&A view ----------
function qaPairs() {
  return D.items.filter(i => i.type === "prompt").map(p => ({ prompt: p, response: p.reply ? BY_ID[p.reply] : null }));
}
function renderQA(p) {
  const q = (p.get("q") || "").trim(), ql = q.toLowerCase(), ph = p.get("qphase") || "", cat = p.get("qcat") || "";
  if (document.activeElement !== $("qa-q")) $("qa-q").value = q;
  $("qa-phase").value = ph; $("qa-cat").value = cat;
  const all = qaPairs();
  const shown = all.filter(({ prompt, response }) => (!ph || prompt.phase === ph) && (!cat || prompt.category === cat)
    && (!ql || prompt.text.toLowerCase().includes(ql) || (response && response.text.toLowerCase().includes(ql))));
  $("qa-count").textContent = `${fmtN(shown.length)} of ${fmtN(all.length)} prompts` +
    (q ? ` match “${q}”` : "") + `. ${fmtN(D.summary.unanswered_prompts)} prompts have no logged response.`;
  const focus = p.get("focus");
  $("qa-list").innerHTML = shown.map(({ prompt: pr, response: r }) => `<li data-id="${esc(pr.id)}"${pr.id === focus ? ' class="focus" tabindex="-1"' : ""}>
    <div class="q">${marker("HUMAN")}<div>
      <div class="meta"><span>${esc(pr.ts.slice(0, 16).replace("T", " "))}</span><span>${esc(pr.phase)}${pr.stage ? ` · ${esc(pr.stage)}` : ""}</span>
        <span>Prompt · category: <strong>${esc(pr.category)}</strong></span><code>${esc(pr.source)}</code></div>
      <pre class="txt">${highlight(pr.text || "(empty prompt)", q)}</pre></div></div>
    <div class="a">${marker("CLAUDE")}<div>${r ? `
      <div class="meta"><span>${esc(r.ts.slice(0, 16).replace("T", " "))}</span><span>Claude's response (excerpt)</span><code>${esc(r.source)}</code></div>
      <pre class="txt">${highlight(r.text || "(no text logged)", q)}</pre>` : `<p class="none">No response logged for this prompt in its session.</p>`}</div></div>
  </li>`).join("") || `<li class="none">No prompts match.</li>`;
  if (focus) {
    const el = document.querySelector(`#qa-list li[data-id="${CSS.escape(focus)}"]`);
    if (el) { el.scrollIntoView({ block: "center" }); el.focus({ preventScroll: true }); }
  }
}
function setupQA() {
  options($("qa-phase"), D.phases, v => v, "All phases");
  options($("qa-cat"), D.categories, c => c, "All categories");
  let timer = null;
  $("qa-q").addEventListener("input", e => {
    clearTimeout(timer);
    timer = setTimeout(() => setHash({ q: e.target.value.trim(), focus: null }, true), 150);
  });
  $("qa-phase").addEventListener("change", e => setHash({ qphase: e.target.value, focus: null }));
  $("qa-cat").addEventListener("change", e => setHash({ qcat: e.target.value, focus: null }));
}

// ---------- summary view ----------
const METRICS = [
  ["prompts", "Prompts"], ["responses", "Responses"], ["approvals", "Approvals (HUMAN decision tags)"],
  ["rejected_plans", "Rejected plans"], ["spec_edits", "Spec edits (per file per commit)"], ["reviews", "Review-log entries"],
  ["commits", "Commits"], ["lines_added", "Lines added (hand-written files)"], ["lines_removed", "Lines removed (hand-written files)"]];
function renderSummary() {
  const S = D.summary, pa = S.per_actor, since = S.rules.rejected_recorded_since.slice(0, 10);
  const cell = (k, a) => {
    const v = pa[a][k];
    if (v === null) return `<td class="n na" title="Not applicable to this actor">—</td>`;
    if (k === "rejected_plans") return `<td class="n" data-k="${k}" data-v="${v}">${fmtN(v)} <span class="fine">since ${esc(since)}; earlier not recorded</span></td>`;
    return `<td class="n" data-k="${k}" data-v="${v}">${fmtN(v)}</td>`;
  };
  $("sum-table").innerHTML = `<caption>Each count is computed by <code>make timeline</code> from the logs and git history.</caption>
    <thead><tr><th scope="col">Measure</th>${D.actors.map(a => `<th scope="col" class="n" data-actor="${a}">${marker(a)} ${esc(ACTOR_LABEL[a])}</th>`).join("")}</tr></thead>
    <tbody>${METRICS.map(([k, label]) => `<tr data-metric="${k}"><th scope="row">${esc(label)}</th>${D.actors.map(a => cell(k, a)).join("")}</tr>`).join("")}</tbody>`;
  $("sum-notes").innerHTML = [S.rules.approvals, S.rules.rejected_plans, S.rules.lines_changed,
    "Commits by prefix: agent: → Claude, human: → Aayush, anything else → shared. Spec edits count as Aayush's even in agent: commits (PROV-02); in commits with neither prefix they are shared.",
    `Claude also logged ${fmtN(S.agent_decisions)} AGENT decision tags in docs/progress.md.`].map(esc).join("<br>");
  const total = Object.values(S.prompt_categories).reduce((a, b) => a + b, 0);
  $("cat-table").innerHTML = `<thead><tr><th scope="col">Category</th><th scope="col" class="n">Prompts</th><th scope="col">Rule</th></tr></thead><tbody>
    ${D.categories.map(c => `<tr data-cat="${esc(c)}"><th scope="row">${esc(c)}</th><td class="n">${fmtN(S.prompt_categories[c])}</td><td>${esc({
      "human-typed": `starts with “${S.rules.human_typed_marker}”`,
      automated: `starts with ${S.rules.automated_prefixes.join(", ")}`,
      shared: "anything else (unclear, so not guessed)" }[c])}</td></tr>`).join("")}</tbody>`;
  $("cat-notes").textContent = `${fmtN(total)} logged prompts in all. ${fmtN(S.qa_pairs)} are paired with a response.`;
  const k = (id, label, value, sub) => `<div class="kpi" id="${id}"><div class="label">${esc(label)}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
  $("sum-kpis").innerHTML =
    k("kpi-prompts", "Prompts from Aayush", fmtN(pa.HUMAN.prompts), `${fmtN(S.qa_pairs)} answered by Claude`) +
    k("kpi-approvals", "Decisions Aayush made", fmtN(pa.HUMAN.approvals), "HUMAN tags in the progress log") +
    k("kpi-commits", "Commits", fmtN(pa.CLAUDE.commits + pa.HUMAN.commits + pa.shared.commits),
      `${fmtN(pa.CLAUDE.commits)} Claude · ${fmtN(pa.HUMAN.commits)} Aayush · ${fmtN(pa.shared.commits)} shared`) +
    k("kpi-specs", "Spec edits", fmtN(pa.HUMAN.spec_edits + pa.shared.spec_edits),
      `${fmtN(pa.HUMAN.spec_edits)} Aayush · ${fmtN(pa.shared.spec_edits)} shared`);
  const body = $("narrative-body");
  if (D.narrative) {
    body.innerHTML = D.narrative.trim().split(/\n\s*\n/).map(block => {
      const h = block.match(/^#{1,6}\s+(.*)$/);
      return h && !block.includes("\n") ? `<h3>${esc(h[1])}</h3>` : `<p>${esc(block)}</p>`;
    }).join("");
  } else {
    body.innerHTML = `<p class="missing" id="narrative-missing">Narrative not yet written. Aayush will add it in <code>docs/timeline-narrative.md</code>.</p>`;
  }
}

// ---------- shell ----------
const VIEWS = ["timeline", "qa", "summary"];
function route() {
  const p = hashParams();
  const view = VIEWS.includes(p.get("view")) ? p.get("view") : "timeline";
  for (const v of VIEWS) {
    $(`view-${v}`).hidden = v !== view;
    $(`tab-${v}`).setAttribute("aria-selected", String(v === view));
    $(`tab-${v}`).tabIndex = v === view ? 0 : -1;
  }
  if (view === "timeline") renderTimeline(p);
  else if (view === "qa") renderQA(p);
  else renderSummary();
}
function setupTabs() {
  const tabs = [...document.querySelectorAll('#tabs [role="tab"]')];
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => setHash({ view: t.dataset.view, focus: null }));
    t.addEventListener("keydown", e => {
      const k = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (k === undefined) return;
      e.preventDefault();
      const next = tabs[(k + tabs.length) % tabs.length];
      next.focus(); setHash({ view: next.dataset.view, focus: null });
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
    const order = ["auto", "light", "dark"];
    const cur = document.documentElement.dataset.theme || "auto";
    const next = order[(order.indexOf(cur) + 1) % order.length];
    if (next === "auto") delete document.documentElement.dataset.theme; else document.documentElement.dataset.theme = next;
    try { if (next === "auto") localStorage.removeItem("dash-theme"); else localStorage.setItem("dash-theme", next); } catch (e) {}
    label();
  });
  label();
}
function fail(e) {
  window.__tl.errors.push(String(e));
  const el = $("load-error");
  el.hidden = false;
  el.textContent = `Could not build the timeline: ${e.message || e}. Serve the site/ folder over HTTP (make serve) so the data file can load.`;
  console.error(e);
}
async function main() {
  try {
    const r = await fetch(DATA_URL);
    if (!r.ok) throw new Error(`timeline.json: HTTP ${r.status}`);
    D = await r.json();
    if (!Array.isArray(D.items) || !D.summary) throw new Error("timeline.json is missing items or summary");
    BY_ID = Object.fromEntries(D.items.map(i => [i.id, i]));
    const first = D.items[0], last = D.items[D.items.length - 1];
    $("run-line").innerHTML = `${fmtN(D.items.length)} items from ${esc(first.ts.slice(0, 10))} to ${esc(last.ts.slice(0, 10))}` +
      (D.head ? `, built at commit <code>${esc(D.head.slice(0, 7))}</code>` : "") + `. ${esc(D.about)}`;
    setupTabs(); setupTheme(); setupTimeline(); setupQA();
    window.addEventListener("hashchange", route);
    route();
    window.__tl.ready = true;
  } catch (e) { fail(e); }
}
main();
