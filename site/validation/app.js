// Validation explorer (P4). Static: reads site/validation/data/*.json, no build step.
// Every number on the page is computed from those files; nothing is typed in by hand.
"use strict";

window.__val = { ready: false, errors: [] };
const DATA = "data/";
const JSON_FILES = ["manifest", "tests", "history", "traceability", "coverage", "faults", "claims"];
const RECOVERY = ["recovery", "rhetoric_recovery", "coder_dev_eval"];
const D = {};
const PHASES = ["P0", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "untagged"];
const STATUS = {  // label + icon: color never carries the meaning alone
  passed: ["✓", "passed"], failed: ["✕", "failed"], error: ["!", "error"], skipped: ["–", "skipped"],
  xfailed: ["~", "xfail"], xpassed: ["!", "xpass"], passing: ["✓", "passing"], failing: ["✕", "failing"],
  partial: ["–", "partial"], untested: ["✕", "no tests"], missing: ["?", "missing"], absent: ["·", "not run"],
};
const LETTER = { p: "passed", f: "failed", e: "error", s: "skipped", x: "xfailed", X: "xpassed", ".": "absent" };

// ---------- helpers ----------
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
const shortSha = s => (s || "").slice(0, 7);
function pill(status, label) {
  const [ic, text] = STATUS[status] || ["?", status];
  return `<span class="pill st-${esc(status)}" data-status="${esc(status)}"><span class="ic" aria-hidden="true">${ic}</span>${esc(label ?? text)}</span>`;
}
function kpi(id, label, value, sub = "") {
  return `<div class="kpi" id="${id}"><div class="label">${esc(label)}</div><div class="value">${value}</div><div class="sub">${sub}</div></div>`;
}
function setHash(params) {
  const h = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") h.set(k, v);
  const next = h.toString();
  if (location.hash.replace(/^#/, "") === next) route(); else location.hash = next;
}
function hashParams() { return new URLSearchParams(location.hash.replace(/^#/, "")); }
function testLink(nodeid, text) {
  const h = new URLSearchParams({ view: "tests", test: nodeid });
  return `<a href="#${esc(h.toString())}" class="tlink">${esc(text ?? nodeid)}</a>`;
}
function runTitle(i, letter) {
  const r = D.history.runs[i];
  return `${r.file} · ${r.started.slice(0, 16).replace("T", " ")} · ${STATUS[LETTER[letter]][1]}`;
}
function strip(letters, { big = false, last = 0 } = {}) {
  const start = last ? Math.max(0, letters.length - last) : 0;
  const cells = [...letters.slice(start)].map((l, k) =>
    `<i class="${l === "." ? "a" : l}" title="${esc(runTitle(start + k, l))}"></i>`).join("");
  const counts = {};
  for (const l of letters.slice(start)) counts[l] = (counts[l] || 0) + 1;
  const name = Object.entries(counts).map(([l, n]) => `${n} ${STATUS[LETTER[l]][1]}`).join(", ");
  return `<span class="strip${big ? " big" : ""}" role="img" aria-label="Run history, oldest first: ${esc(name)}">${cells}</span>`;
}
function stripLegend() {
  return `<div class="legend" aria-hidden="true">${["p", "f", "s", "x", "."].map(l =>
    `<span><span class="strip"><i class="${l === "." ? "a" : l}"></i></span> ${STATUS[LETTER[l]][1]}</span>`).join("")}</div>`;
}
function paragraphs(text) {  // reflow hard-wrapped docstring lines; blank lines separate paragraphs
  return text.split(/\n\s*\n/).map(par => `<p>${esc(par.replace(/\s*\n\s*/g, " "))}</p>`).join("");
}
function options(sel, values, all = "Any") {
  sel.innerHTML = [`<option value="">${all}</option>`, ...values.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`)].join("");
}

// ---------- Tests (VAL-01, VAL-02, VAL-05) ----------
const T = { byId: {}, req: {} };
function buildTests() {
  const tests = D.tests.tests;
  T.byId = Object.fromEntries(tests.map(t => [t.nodeid, t]));
  T.req = Object.fromEntries(D.traceability.requirements.map(r => [r.id, r]));
  const s = D.tests.summary, n = D.tests.n;
  const bad = (s.failed || 0) + (s.error || 0);
  $("test-kpis").innerHTML =
    kpi("k-tests", "Tests in snapshot run", `<span data-k="n">${n}</span>`, `${s.passed || 0} passed · ${bad} failed or errored · ${s.skipped || 0} skipped`) +
    kpi("k-runs", "Runs in history", `<span data-k="runs">${D.history.runs.length}</span>`, `since ${esc(D.history.runs[0].started.slice(0, 10))}; every run file is kept`) +
    kpi("k-reqs", "Requirements with tests", `<span data-k="reqs">${D.traceability.requirements.filter(r => r.tests.length).length}</span> of ${D.traceability.requirements.length}`, "see Traceability");
  const present = new Set(tests.map(t => t.phase));
  options($("f-phase"), PHASES.filter(p => present.has(p)).map(p => [p, p]));
  options($("f-kind"), [...new Set(tests.map(t => t.kind))].sort().map(k => [k, k]));
  options($("f-status"), [...new Set(tests.map(t => t.status))].sort().map(k => [k, STATUS[k][1]]));
  options($("f-req"), D.traceability.requirements.filter(r => r.tests.length).map(r => [r.id, r.id]));
  const update = () => setHash({ view: "tests", ...readFilters(), test: hashParams().get("test") });
  for (const id of ["f-phase", "f-kind", "f-status", "f-req"]) $(id).addEventListener("change", update);
  let timer;
  $("f-q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(update, 150); });
  $("f-clear").addEventListener("click", () => setHash({ view: "tests" }));
  $("test-table").addEventListener("click", e => {
    if (e.target.closest("a")) return;
    const tr = e.target.closest("tr[data-nodeid]");
    if (tr) setHash({ view: "tests", ...readFilters(), test: tr.dataset.nodeid });
  });
  $("test-table").addEventListener("keydown", e => {
    const tr = e.target.closest("tr[data-nodeid]");
    if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); tr.click(); }
  });
}
function readFilters() {
  return { q: $("f-q").value.trim(), phase: $("f-phase").value, kind: $("f-kind").value,
           status: $("f-status").value, req: $("f-req").value };
}
function writeFilters(p) {
  for (const k of ["q", "phase", "kind", "status", "req"]) {
    const el = $(`f-${k}`), v = p.get(k) || "";
    if (k !== "q" && v && ![...el.options].some(o => o.value === v)) continue;
    if (el.value !== v && !(k === "q" && document.activeElement === el)) el.value = v;
  }
}
function filterTests(f) {
  const q = f.q.toLowerCase();
  return D.tests.tests.filter(t =>
    (!f.phase || t.phase === f.phase) && (!f.kind || t.kind === f.kind) && (!f.status || t.status === f.status) &&
    (!f.req || t.req_ids.includes(f.req)) &&
    (!q || t.nodeid.toLowerCase().includes(q) || t.docstring.toLowerCase().includes(q) || t.source.toLowerCase().includes(q)));
}
function renderTests(p) {
  writeFilters(p);
  const f = readFilters();
  const rows = filterTests(f);
  const selected = p.get("test");
  $("test-count").textContent = `Showing ${rows.length} of ${D.tests.n} tests`;
  $("test-count").dataset.shown = rows.length;
  $("test-table").querySelector("tbody").innerHTML = rows.map(t => `
    <tr data-nodeid="${esc(t.nodeid)}" tabindex="0" aria-selected="${t.nodeid === selected}">
      <td>${pill(t.status)}</td><td class="nodeid">${esc(t.nodeid)}
        <div class="tmeta">${t.req_ids.map(esc).join(", ") || "no requirement"} · ${esc(t.kind)} · ${t.duration_s.toFixed(3)} s</div></td><td>${strip(D.history.tests[t.nodeid], { last: 20 })}</td>
    </tr>`).join("");
  renderDetail(selected);
}
function renderDetail(nodeid) {
  const el = $("test-detail");
  const t = T.byId[nodeid];
  if (!t) {
    el.innerHTML = nodeid ? `<p class="error">No test ${esc(nodeid)} in the snapshot run.</p>`
      : '<p class="fine">Select a test to see its docstring, source, history and the spec text it covers.</p>';
    return;
  }
  const letters = D.history.tests[t.nodeid];
  const ran = [...letters].filter(l => l !== ".").length, passed = [...letters].filter(l => l === "p").length;
  const reqs = t.req_ids.map(id => {
    const r = T.req[id];
    return r ? `<div class="reqbox"><strong>${esc(id)}</strong> <span class="fine">${esc(r.spec)}</span>
      <div class="reqtext">${esc(r.text)}</div></div>` : `<div class="reqbox">${esc(id)} (not in any spec)</div>`;
  }).join("") || '<p class="fine">This test is not tagged with a requirement.</p>';
  el.innerHTML = `
    <h3 id="detail-title">${esc(t.nodeid)}</h3>
    <p>${pill(t.status)}</p>
    <dl>
      <dt>File</dt><dd>${esc(t.file)}:${esc(t.line)}</dd>
      <dt>Phase</dt><dd>${esc(t.phase)}</dd><dt>Kind</dt><dd>${esc(t.kind)}</dd>
      <dt>Duration</dt><dd>${t.duration_s.toFixed(3)} s</dd>
      <dt>Body</dt><dd><code title="${esc(t.body_sha256)}">${shortSha(t.body_sha256)}</code> (SHA-256 of docstring + source)</dd>
    </dl>
    <h4>What it proves (docstring)</h4>
    <div class="doc" id="detail-doc">${t.docstring ? paragraphs(t.docstring) : '<p class="bad">No docstring.</p>'}</div>
    ${t.failure_message ? `<h4>Failure message</h4><pre class="code msg" id="detail-msg">${esc(t.failure_message)}</pre>` : ""}
    <h4>History</h4>
    <p class="fine" id="detail-hist">Passed in ${passed} of the ${ran} runs it was part of (of ${letters.length} runs in total).</p>
    ${strip(letters, { big: true })}${stripLegend()}
    <h4>Requirements it covers</h4>${reqs}
    <h4>Source</h4><pre class="code" id="detail-src">${esc(t.source)}</pre>`;
}

// ---------- Traceability (VAL-03) ----------
function buildTrace() {
  const T3 = D.traceability, c = T3.counts;
  $("trace-intro").innerHTML = `Every requirement line in <code>specs/*.md</code>, with the tests tagged
    <code>@pytest.mark.req</code> for it and their status in the snapshot run. Requirements with no tests are red, including those
    in phases that have not started yet (current phase: <code>${esc(T3.current_phase)}</code>).`;
  $("trace-kpis").innerHTML = ["passing", "partial", "failing", "untested"].map(s =>
    kpi(`k-${s}`, STATUS[s][1][0].toUpperCase() + STATUS[s][1].slice(1), `<span data-k="${s}">${c[s] || 0}</span>`,
        s === "untested" ? "red below" : "")).join("");
  options($("t-phase"), PHASES.filter(p => T3.requirements.some(r => r.phase === p)).map(p => [p, p]));
  options($("t-status"), ["passing", "partial", "failing", "untested"].map(s => [s, STATUS[s][1]]));
  const update = () => setHash({ view: "trace", phase: $("t-phase").value, status: $("t-status").value });
  $("t-phase").addEventListener("change", update);
  $("t-status").addEventListener("change", update);
}
function renderTrace(p) {
  $("t-phase").value = p.get("phase") || "";
  $("t-status").value = p.get("status") || "";
  const rows = D.traceability.requirements.filter(r =>
    (!$("t-phase").value || r.phase === $("t-phase").value) && (!$("t-status").value || r.status === $("t-status").value));
  $("trace-count").textContent = `Showing ${rows.length} of ${D.traceability.requirements.length} requirements`;
  $("trace-count").dataset.shown = rows.length;
  $("trace-table").querySelector("tbody").innerHTML = rows.map(r => `
    <tr id="req-${esc(r.id)}" class="${esc(r.status)}" data-req="${esc(r.id)}" data-status="${esc(r.status)}">
      <td class="rid">${esc(r.id)}<br><span class="fine">${esc(r.phase)}</span>${r.phase_started ? "" : '<span class="badge">phase not started</span>'}</td>
      <td>${pill(r.status)}</td>
      <td class="reqtext">${esc(r.text)}</td>
      <td class="n">${r.tests.length ? `<a href="#${new URLSearchParams({ view: "tests", req: r.id })}">${r.tests.length}</a>` : "0"}</td>
    </tr>`).join("");
  const focus = p.get("req");
  if (focus && $(`req-${focus}`)) $(`req-${focus}`).scrollIntoView({ block: "center" });
}

// ---------- Coverage (VAL-03) ----------
function buildCoverage() {
  const C = D.coverage;
  $("cov-intro").innerHTML = `Line coverage of <code>src/</code> measured by ${esc(C.source.split(",")[0])} (coverage ${esc(C.coverage_version)})
    during the snapshot run <code>${esc(C.run)}</code>.`;
  const low = C.modules.filter(m => m.statements > 0 && m.percent < 80).length;
  $("cov-kpis").innerHTML =
    kpi("k-cov", "Total line coverage", `<span data-k="total">${C.totals.percent.toFixed(1)}%</span>`, `${C.totals.statements - C.totals.missing} of ${C.totals.statements} statements`) +
    kpi("k-mods", "Modules", `<span data-k="modules">${C.modules.length}</span>`, `${low} below 80%`);
  $("cov-table").querySelector("tbody").innerHTML = C.modules.map(m => `
    <tr data-module="${esc(m.module)}"><td><code>${esc(m.module)}</code></td><td class="n">${m.statements}</td><td class="n">${m.missing}</td>
      <td class="n">${m.percent.toFixed(1)}%</td>
      <td><span class="meter" role="img" aria-label="${m.percent.toFixed(1)}% covered"><b style="width:${m.percent}%"></b></span></td></tr>`).join("");
}

// ---------- Faults (VAL-04) ----------
function buildFaults() {
  const F = D.faults;
  if (!F) { $("fault-method").innerHTML = '<p class="error">results/faults.json is missing: run <code>make faults</code>.</p>'; return; }
  $("fault-kpis").innerHTML =
    kpi("k-rate", "Fault detection rate", `<span data-k="rate">${pct(F.detection_rate)}</span>`, `${F.n_caught} of ${F.n_faults} faults caught by at least one test`) +
    kpi("k-brate", "Caught by a behavioural test", `<span data-k="brate">${pct(F.behavioral_detection_rate)}</span>`, `${F.n_caught_behavioral} of ${F.n_faults}; the rest only by golden-file tests`) +
    kpi("k-uncaught", "Uncaught faults", `<span data-k="uncaught">${F.uncaught.length}</span>`, "listed below, never hidden");
  $("fault-method").innerHTML = `<p><strong>Method.</strong> ${esc(F.method)}</p>
    <p><strong>UI tests.</strong> ${esc(F.ui_policy)}</p>
    <p><strong>Golden-file vs behavioural.</strong> ${esc(F.golden_definition)}</p>
    <p class="fine">Generated ${esc(F.generated)} at commit <code>${shortSha(F.git_commit)}</code>. Baseline: ${F.baseline.n_tests} tests
      (${F.baseline.n_tests_with_ui ?? "–"} with UI tests), all passing before any fault was applied.</p>`;
  const byId = Object.fromEntries(F.faults.map(f => [f.id, f]));
  $("fault-uncaught").innerHTML = F.uncaught.length
    ? `<span class="bad">${F.uncaught.map(id => `${esc(id)} ${esc(byId[id].title)}`).join("; ")}</span>`
    : `<span class="ok">None.</span> All ${F.n_faults} faults made at least one test fail.`;
  $("fault-golden").innerHTML = F.golden_only.length
    ? `${F.golden_only.map(id => `<strong>${esc(id)}</strong> ${esc(byId[id].title)}`).join("; ")}. A committed output changed, but no test
       checks the property that broke.` : "None.";
  $("fault-list").innerHTML = F.faults.map(f => `
    <li class="fault ${f.caught ? "caught" : "uncaught"}" id="fault-${esc(f.id)}" data-fault="${esc(f.id)}">
      <div class="head"><strong>${esc(f.id)}</strong> ${esc(f.title)} ${pill(f.caught ? "passing" : "failing", f.caught ? "caught" : "not caught")}
        ${f.golden_only ? '<span class="tag">golden-file only</span>' : ""}${f.ui_tests_included ? '<span class="tag">UI tests included</span>' : ""}</div>
      <div class="meta">${esc(f.category)} · <code>${esc(f.file)}</code> · ${f.n_tests_run} tests run · ${f.duration_s}s</div>
      <p>${esc(f.description)}</p>
      <div class="diff"><code class="del">${esc(f.old)}</code><code class="add">${esc(f.new)}</code></div>
      ${f.caught_by.length ? `<details><summary>Caught by ${f.n_caught_by} test${f.n_caught_by === 1 ? "" : "s"}</summary><ul class="catchers">${
        f.caught_by.map(n => `<li>${T.byId[n] ? testLink(n) : esc(n)}<span class="tag">${f.caught_by_golden.includes(n) ? "golden-file" : "behavioural"}</span></li>`).join("")}</ul></details>` : ""}
    </li>`).join("");
}

// ---------- Claims (VAL-06) ----------
function buildClaims() {
  const C = D.claims;
  if (!C) { $("claims-intro").innerHTML = '<span class="error">claims.json is missing.</span>'; return; }
  $("claims-intro").textContent = C.note;
  $("claim-list").innerHTML = C.claims.map(c => `
    <li class="claim" id="claim-${esc(c.id)}" data-claim="${esc(c.id)}">
      <div class="head"><strong>${esc(c.title)}</strong> ${pill(c.status)}
        <a href="../dashboard/#view=${esc(c.dashboard_view)}">open on the dashboard</a></div>
      <p>${esc(c.claim)}</p>
      <ul>${c.tests.map(n => `<li>${pill(c.test_status[n])} ${T.byId[n] ? testLink(n) : esc(n)}</li>`).join("")}</ul>
    </li>`).join("");
}
function renderClaims(p) {
  const id = p.get("claim");
  document.querySelectorAll(".claim").forEach(el => el.classList.toggle("focus", el.dataset.claim === id));
  if (id && $(`claim-${id}`)) $(`claim-${id}`).scrollIntoView({ block: "start" });
}

// ---------- Recovery vs. ground truth (validation only) ----------
function yesno(v) { return v ? '<span class="ok">✓ recovered</span>' : '<span class="bad">✕ not recovered</span>'; }
function buildRecovery() {
  const R = D.recovery, H = D.rhetoric_recovery, E = D.coder_dev_eval;
  const dirs = Object.entries(R.directions).map(([id, d]) => `<tr data-claim="${esc(id)}"><td>${esc(id)}</td><td style="white-space:normal">${esc(d.claim)}</td><td>${yesno(d.recovered)}</td></tr>`);
  const nulls = Object.entries(R.null).map(([id, d]) => `<tr data-claim="${esc(id)}"><td>${esc(id)}</td><td style="white-space:normal">${esc(d.claim)}
    (clustered p = ${d.p_clustered.toFixed(3)}; naive p = ${d.p_naive.toFixed(3)})</td><td>${yesno(d.recovered)}</td></tr>`);
  const mags = R.magnitude.ratios.map(m => `<tr><td>${esc(m.ratio)}</td><td class="n">${m.planted}</td><td class="n">${m.estimate.toFixed(2)}</td>
    <td class="n">${m.ci[0].toFixed(2)} to ${m.ci[1].toFixed(2)}</td><td class="n">${pct(m.relative_error, 1)}</td><td>${m.within_tolerance ? '<span class="ok">✓ yes</span>' : '<span class="bad">✕ no</span>'}</td></tr>`);
  const labels = Object.entries(E.scores.labels).map(([k, v]) => `<tr><td>${esc(k)}</td><td class="n">${v.precision.toFixed(2)}</td><td class="n">${v.recall.toFixed(2)}</td><td class="n">${v.f1.toFixed(2)}</td><td class="n">${v.support}</td></tr>`);
  $("recovery-body").innerHTML = `
    <div class="grid">
      <div class="panel" id="rec-planted"><h3>Planted effects (${esc(R.requirement)})</h3>
        <p class="takeaway">${Object.values(R.directions).filter(d => d.recovered).length} of ${Object.keys(R.directions).length} planted directions and
          ${Object.values(R.null).filter(d => d.recovered).length} of ${Object.keys(R.null).length} planted null recovered.</p>
        <div class="table-wrap"><table><thead><tr><th>Truth</th><th>Planted claim</th><th>Result</th></tr></thead><tbody>${dirs.join("")}${nulls.join("")}</tbody></table></div>
        <h4>Magnitudes (tolerance ±${pct(R.magnitude.tolerance)})</h4>
        <div class="table-wrap"><table><thead><tr><th>Ratio</th><th class="n">Planted</th><th class="n">Estimate</th><th class="n">95% CI</th><th class="n">Rel. error</th><th>Within</th></tr></thead><tbody>${mags.join("")}</tbody></table></div>
        <p class="panel-note">CI coverage of planted coefficients across seeds ${R.coverage.seeds.join(", ")}: ${R.coverage.all_met ? '<span class="ok">all met</span>' : '<span class="bad">not all met</span>'} (minimum ${R.coverage.min_covered} of ${R.coverage.seeds.length} seeds).</p>
      </div>
      <div class="panel" id="rec-rhetoric"><h3>Rhetoric-gap flags (${esc(H.requirement)})</h3>
        <p class="takeaway">Of ${H.n_listed} institutions listed in the top decile, ${H.hits.length} have a planted rhetoric gap
          (precision ${H.precision.toFixed(2)}, base rate ${H.base_rate.toFixed(2)}); ${H.direction_correct} have the right direction.
          Recall over flagged-eligible institutions: ${H.recall.toFixed(2)}.</p>
      </div>
      <div class="panel" id="rec-coder"><h3>Keyword coder on the dev split (${esc(E.requirement)})</h3>
        <p class="takeaway">On the ${E.scores.n} dev statements used to write the rules: stance accuracy ${E.scores.stance.accuracy.toFixed(2)},
          macro-F1 ${E.scores.macro_f1.toFixed(2)}. Held-out accuracy (the honest number) is on the dashboard's Coder accuracy view.</p>
        <div class="table-wrap"><table><thead><tr><th>Theme</th><th class="n">Precision</th><th class="n">Recall</th><th class="n">F1</th><th class="n">n</th></tr></thead><tbody>${labels.join("")}</tbody></table></div>
      </div>
    </div>
    <details class="panel-note"><summary>Raw files</summary>${RECOVERY.map(f => `<h4>${f}.json</h4><pre class="code">${esc(JSON.stringify(D[f], null, 1))}</pre>`).join("")}</details>`;
}

// ---------- Review log (VAL-07) ----------
function buildReview() {
  if (typeof marked === "undefined" || typeof DOMPurify === "undefined") throw new Error("marked/DOMPurify did not load (check the network)");
  $("review-body").innerHTML = DOMPurify.sanitize(marked.parse(D.reviewLog));
  const s = D.tests.summary, c = D.traceability.counts, F = D.faults;
  $("review-side").innerHTML = `<h3>Automated evidence, same snapshot</h3>
    <p>${pill((s.failed || s.error) ? "failing" : "passing", `${s.passed || 0} of ${D.tests.n} tests passed`)}</p>
    <p>${c.passing || 0} requirements passing, ${c.partial || 0} partial, ${c.failing || 0} failing, <span class="bad">${c.untested || 0} with no tests</span>.</p>
    ${F ? `<p>Fault detection: ${F.n_caught} of ${F.n_faults} (${F.n_caught_behavioral} by a behavioural test).</p>` : ""}
    <p class="fine">Manual reviews check what tests can't: whether the hooks fired in a real session, whether the numbers make sense, and whether the docs match the sources.</p>`;
}

// ---------- routing ----------
const VIEWS = { tests: [buildTests, renderTests], trace: [buildTrace, renderTrace], coverage: [buildCoverage],
                faults: [buildFaults], claims: [buildClaims, renderClaims], recovery: [buildRecovery], review: [buildReview] };
const built = new Set();
function show(view, p) {
  document.querySelectorAll('[role="tab"]').forEach(t => {
    const on = t.dataset.view === view;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll('[role="tabpanel"]').forEach(el => { el.hidden = el.id !== `view-${view}`; });
  if (!built.has("tests")) { buildTests(); built.add("tests"); }  // other views link to tests by node ID
  if (!built.has(view)) { VIEWS[view][0](); built.add(view); }
  if (VIEWS[view][1]) VIEWS[view][1](p);
}
function route() {
  const p = hashParams();
  const view = VIEWS[p.get("view")] ? p.get("view") : "tests";
  try { show(view, p); } catch (e) { fail(e); }
}
function setupTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => setHash({ view: t.dataset.view }));
    t.addEventListener("keydown", e => {
      const k = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (k === undefined) return;
      e.preventDefault();
      const next = tabs[(k + tabs.length) % tabs.length];
      next.focus(); setHash({ view: next.dataset.view });
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
  window.__val.errors.push(String(e));
  const el = $("load-error");
  el.hidden = false;
  el.textContent = `Could not build the explorer: ${e.message || e}. Serve the site/ folder over HTTP (make serve) so the data files can load.`;
  console.error(e);
}

async function getJSON(path, optional = false) {
  const r = await fetch(DATA + path);
  if (!r.ok) { if (optional && r.status === 404) return null; throw new Error(`${path}: HTTP ${r.status}`); }
  return r.json();
}
async function main() {
  try {
    await Promise.all([
      ...JSON_FILES.map(async f => { D[f] = await getJSON(`${f}.json`, f === "faults" || f === "claims"); }),
      ...RECOVERY.map(async f => { D[f] = await getJSON(`recovery/${f}.json`); }),
      (async () => { const r = await fetch(DATA + "review-log.md"); if (!r.ok) throw new Error(`review-log.md: HTTP ${r.status}`); D.reviewLog = await r.text(); })(),
    ]);
    for (const f of [...JSON_FILES, ...RECOVERY]) if (D[f] && D[f].synthetic !== true) throw new Error(`${f}.json is not marked synthetic`);
    const m = D.manifest;
    $("run-line").innerHTML = `Snapshot run <code>${esc(m.run)}</code>, started ${esc(D.tests.started.slice(0, 19).replace("T", " "))},
      commit <code>${shortSha(D.tests.git_commit)}</code>${D.tests.git_dirty ? " (with uncommitted changes)" : ""}. ${m.n_runs} runs in history.
      <span class="fine">${esc(D.tests.redaction)}</span>`;
    setupTabs(); setupTheme();
    window.addEventListener("hashchange", route);
    route();
    window.__val.ready = true;
  } catch (e) { fail(e); }
}
main();
