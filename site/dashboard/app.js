/* Findings dashboard (P3). SYNTHETIC DATA: every institution, course and statement is invented.
 *
 * Every number shown comes from site/data/*.json (copied from results/ by `make report`). Numbers in text and
 * tables are wrapped in <span data-src="file.json#/json/pointer" data-fmt="..."> and every chart dataset carries
 * `srcs` (one JSON pointer per value), so tests/test_dash_ui.py can check each displayed number against its source.
 */
"use strict";

const DATA_DIR = "../data/";
const FILES = ["descriptives", "allowed_uses", "assessment", "association", "regression", "rhetoric",
               "coder_eval", "kappa", "institutions", "courses", "statements"];
const D = {};
const charts = {};            // id -> Chart
const builtViews = new Set();
window.__dash = { charts, ready: false, errors: [] };

const POLICY_LABELS = ["0 Prohibited", "1 Limited use", "2 Permitted with disclosure", "3 Encouraged", "4 Integrated / required"];
const STANCE_LABELS = { "-2": "−2 Prohibitive", "-1": "−1 Cautious", "0": "0 Neutral", "1": "+1 Supportive", "2": "+2 Enthusiastic" };
const THEMES = [["mentions_integrity", "Integrity"], ["mentions_collaboration", "Collaboration"], ["mentions_careers", "Careers"]];
const USES = [["explanation", "Explanation"], ["debugging", "Debugging"], ["code_generation", "Code generation"],
              ["testing", "Testing"], ["writing", "Writing"]];
const ASSESS = [["none", "None"], ["in_class_exams", "In-class exams"], ["oral_defense", "Oral defense"],
                ["process_logs", "Process logs"], ["ai_critique", "AI critique"]];
const REGIONS = ["Northeast", "Midwest", "South", "West"];
const COEF_LABELS = { intermediate: "Intermediate (vs intro)", upper: "Upper (vs intro)", graduate: "Graduate (vs intro)",
  is_se: "SE course", term_index: "Per term", private: "Private (vs public)", R2: "R2 (vs R1)",
  Masters: "Masters (vs R1)", Baccalaureate: "Baccalaureate (vs R1)" };

// ---------- formatting and provenance ----------
const FMT = {
  int: v => String(Math.round(v)),
  f2: v => v.toFixed(2),
  f3: v => v.toFixed(3),
  pct0: v => (v * 100).toFixed(0) + "%",
  pct1: v => (v * 100).toFixed(1) + "%",
  pp0: v => (v * 100).toFixed(0),
  p3: v => (v < 0.001 ? "<0.001" : v.toFixed(3)),
};
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

/** Resolve "file.json#/a/0/b" against the loaded data. */
function get(src) {
  const [file, ptr] = src.split("#");
  let o = D[file.replace(/\.json$/, "")];
  for (const part of ptr.split("/").slice(1)) o = o[Array.isArray(o) ? Number(part) : part];
  return o;
}
/** A displayed number: formatted value plus its JSON source. */
function num(src, fmt) {
  const v = get(src);
  if (typeof v !== "number") throw new Error(`not a number at ${src}`);
  return `<span class="num" data-src="${src}" data-fmt="${fmt}">${FMT[fmt](v)}</span>`;
}
/** Find one record in file[key] (an array) matching every field of `match`; returns its pointer. */
function find(file, key, match) {
  const arr = key.split("/").reduce((o, k) => o[k], D[file]);
  const i = arr.findIndex(r => Object.entries(match).every(([k, v]) => r[k] === v));
  if (i < 0) throw new Error(`no record in ${file}/${key} matching ${JSON.stringify(match)}`);
  return `${file}.json#/${key}/${i}`;
}
const ciText = (p, fmt) => `${num(p + "/ci_low", fmt)}–${num(p + "/ci_high", fmt)}`;

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

// ---------- Chart.js shared setup ----------
/** Draws 95% CI whiskers for datasets that carry `ci: [[lo, hi], ...]`. */
const ciPlugin = {
  id: "ciWhiskers",
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    chart.data.datasets.forEach((ds, di) => {
      if (!ds.ci || !chart.isDatasetVisible(di)) return;
      const meta = chart.getDatasetMeta(di);
      const horizontal = chart.options.indexAxis === "y";
      const vScale = horizontal ? chart.scales.x : chart.scales.y;
      ctx.save();
      ctx.strokeStyle = css("--ink");
      ctx.lineWidth = 1.5;
      meta.data.forEach((el, i) => {
        const [lo, hi] = ds.ci[i];
        const a = vScale.getPixelForValue(lo), b = vScale.getPixelForValue(hi);
        const c = horizontal ? el.y : el.x, cap = 4;
        ctx.beginPath();
        if (horizontal) { ctx.moveTo(a, c); ctx.lineTo(b, c); ctx.moveTo(a, c - cap); ctx.lineTo(a, c + cap); ctx.moveTo(b, c - cap); ctx.lineTo(b, c + cap); }
        else { ctx.moveTo(c, a); ctx.lineTo(c, b); ctx.moveTo(c - cap, a); ctx.lineTo(c + cap, a); ctx.moveTo(c - cap, b); ctx.lineTo(c + cap, b); }
        ctx.stroke();
      });
      ctx.restore();
    });
  },
};

/** Sequential blue ramp for the heatmap (light: pale -> deep; dark: deep -> pale), binned into 7 steps. */
const SEQ = {
  light: ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"],
  dark: ["#13284a", "#184f95", "#256abf", "#2a78d6", "#5598e7", "#86b6ef", "#cde2fb"],
};
function seqStep(v) {
  const ramp = SEQ[document.documentElement.dataset.resolvedTheme === "dark" ? "dark" : "light"];
  const k = Math.min(ramp.length - 1, Math.max(0, Math.floor(v * ramp.length)));
  // ink: white on the deep half of the light ramp; near-black on the pale half of the dark ramp
  const dark = document.documentElement.dataset.resolvedTheme === "dark";
  const ink = dark ? (k >= 4 ? "#0b0b0b" : "#f0efec") : (k >= 3 ? "#ffffff" : "#0b0b0b");
  return { fill: ramp[k], ink };
}

/** Writes the share inside each heatmap cell (a direct label: 20 cells, read as a table). */
const cellLabelPlugin = {
  id: "cellLabels",
  afterDatasetsDraw(chart) {
    const { ctx } = chart;
    const ds = chart.data.datasets[0];
    ctx.save();
    ctx.font = "600 12px system-ui, -apple-system, 'Segoe UI', sans-serif";
    ctx.textAlign = "center"; ctx.textBaseline = "middle";
    chart.getDatasetMeta(0).data.forEach((el, i) => {
      const v = ds.data[i].v;
      ctx.fillStyle = seqStep(v).ink;
      ctx.fillText(FMT.pct0(v), el.x + el.width / 2, el.y + el.height / 2);
    });
    ctx.restore();
  },
};

function baseOptions(extra = {}) {
  const ink2 = css("--ink-2"), grid = css("--grid");
  return deepMerge({
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: "nearest", intersect: true },
    plugins: {
      legend: { position: "bottom", labels: { color: ink2, boxWidth: 12, boxHeight: 12, usePointStyle: false, font: { size: 12 } } },
      tooltip: { backgroundColor: css("--surface"), titleColor: css("--ink"), bodyColor: css("--ink"),
                 borderColor: css("--axis"), borderWidth: 1, padding: 8 },
    },
    scales: {
      x: { ticks: { color: ink2 }, grid: { color: grid }, border: { color: css("--axis") } },
      y: { ticks: { color: ink2 }, grid: { color: grid }, border: { color: css("--axis") } },
    },
  }, extra);
}
function deepMerge(a, b) {
  for (const [k, v] of Object.entries(b)) {
    if (v && typeof v === "object" && !Array.isArray(v) && typeof a[k] === "object" && a[k] && !Array.isArray(a[k])) deepMerge(a[k], v);
    else a[k] = v;
  }
  return a;
}
function makeChart(id, config) {
  if (charts[id]) charts[id].destroy();
  const canvas = document.getElementById(id);
  charts[id] = new Chart(canvas, config);
  return charts[id];
}
const pctTick = v => (v * 100).toFixed(0) + "%";
const fmtCI = (v, ci, f) => `${f(v)} (95% CI ${f(ci[0])}–${f(ci[1])})`;

// ---------- panels ----------
/** Panel scaffold: title, one-sentence takeaway, chart(s), data-table toggle, JSON source link(s). */
function panel(container, { id, title, takeaway, canvases, table, sources, note, size }) {
  const el = document.createElement("article");
  el.className = "panel";
  el.id = `panel-${id}`;
  const plain = takeaway.replace(/<[^>]+>/g, "");
  const charts = canvases.length === 1
    ? `<div class="chart ${size || ""}"><canvas id="${canvases[0].id}" role="img" aria-label="${esc(title + ". " + plain)}"></canvas></div>`
    : `<div class="pair">${canvases.map(c => `<div><h4>${esc(c.title)}</h4><div class="chart ${size || "short"}"><canvas id="${c.id}" role="img" aria-label="${esc(c.title + ". " + plain)}"></canvas></div></div>`).join("")}</div>`;
  el.innerHTML = `<h3>${esc(title)}</h3><p class="takeaway">${takeaway}</p>${charts}
    ${note ? `<p class="panel-note">${note}</p>` : ""}
    <div class="panel-foot">
      <button type="button" class="btn table-toggle" aria-expanded="false" aria-controls="table-${id}">Show data table</button>
      <span>Source: ${sources.map(s => `<a href="${DATA_DIR}${s}.json">${s}.json</a>`).join(", ")}</span>
    </div>
    <p class="panel-note">${evidence(id)}</p>
    <div class="table-wrap" id="table-${id}" hidden>${table}</div>`;
  el.querySelector(".table-toggle").addEventListener("click", e => {
    const wrap = el.querySelector(".table-wrap"), open = wrap.hidden;
    wrap.hidden = !open;
    e.currentTarget.setAttribute("aria-expanded", String(open));
    e.currentTarget.textContent = open ? "Hide data table" : "Show data table";
  });
  container.appendChild(el);
}
// VAL-06: every finding links to the tests that support it, on the validation explorer's Claims view.
function evidence(claimId) {
  return `<a class="evidence" href="../validation/#view=claims&amp;claim=${claimId}">Evidence: supporting tests</a>`;
}
function tableHTML(caption, head, rows) {
  return `<table><caption>${esc(caption)}</caption><thead><tr>${head.map((h, i) => `<th${i ? ' class="n"' : ""} scope="col">${h}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r => `<tr>${r.map((c, i) => i ? `<td class="n">${c}</td>` : `<th scope="row">${c}</th>`).join("")}</tr>`).join("")}</tbody></table>`;
}
const shareCell = (p, fmt = "pct1") => `${num(p + "/estimate", fmt)} <span class="fine">(${ciText(p, fmt)})</span>`;

// ---------- view: summary ----------
function buildSummary() {
  const c = "descriptives.json#/courses", s = "descriptives.json#/statements";
  const allMean = find("descriptives", "policy", { by: "all", category: "mean" });
  const ho = "coder_eval.json#/heldout";
  const tiles = [  // [label, value, sub, claim id]
    ["Course-term rows", num(c + "/n_rows", "int"), `${num(c + "/n_known_policy", "int")} with a stated policy; ${num(c + "/n_excluded_missing_policy", "int")} blank and excluded`, "kpi-rows"],
    ["Institutions", num("regression.json#/n_clusters", "int"), "fictional CS departments; the unit for every clustered interval", "kpi-institutions"],
    ["Official statements", num(s + "/n", "int"), `from ${num(s + "/n_institutions", "int")} institutions, coded by the rule-based coder`, "kpi-statements"],
    ["Mean course policy (0–4)", num(allMean + "/estimate", "f2"), `95% CI ${ciText(allMean, "f2")}; 2 = permitted with disclosure`, "kpi-mean-policy"],
    ["Coder macro-F1, held-out", num(ho + "/macro_f1", "f3"), `target ${num("coder_eval.json#/target_macro_f1", "f2")} · ${D.coder_eval.target_met ? "met" : "not met"}`, "kpi-macro-f1"],
    ["Rhetoric vs practice, r", num("rhetoric.json#/correlation/pearson_r", "f2"),
     `95% CI ${num("rhetoric.json#/correlation/ci/0", "f2")} to ${num("rhetoric.json#/correlation/ci/1", "f2")} across ${num("rhetoric.json#/n_institutions", "int")} institutions`, "kpi-rhetoric-r"],
  ];
  document.getElementById("kpis").innerHTML = tiles.map(([l, v, sub, claim]) =>
    `<div class="kpi" data-claim="${claim}"><div class="label">${l}</div><div class="value">${v}</div><div class="sub">${sub}</div>
      <div class="sub">${evidence(claim)}</div></div>`).join("");
  document.getElementById("summary-note").innerHTML =
    `Intervals are 95% cluster-bootstrap intervals (${num("descriptives.json#/bootstrap/resamples", "int")} resamples of whole institutions), ` +
    `because courses in the same department are not independent. Sources: <a href="${DATA_DIR}descriptives.json">descriptives.json</a>, ` +
    `<a href="${DATA_DIR}coder_eval.json">coder_eval.json</a>, <a href="${DATA_DIR}rhetoric.json">rhetoric.json</a>, <a href="${DATA_DIR}regression.json">regression.json</a>.`;
}

// ---------- view: course policy ----------
function policyShares(by, groups) {
  return POLICY_LABELS.map((label, k) => {
    const ptrs = groups.map(g => find("descriptives", "policy", { by, group: g, category: String(k) }));
    return { label, ptrs };
  });
}
function stackedConfig(groupLabels, series, colors, title) {
  return {
    type: "bar",
    data: {
      labels: groupLabels,
      datasets: series.map((s, k) => ({
        label: s.label, backgroundColor: colors[k], borderColor: css("--surface"), borderWidth: { left: 0, right: 2, top: 0, bottom: 0 },
        data: s.ptrs.map(p => get(p + "/estimate")), srcs: s.ptrs.map(p => p + "/estimate"),
        cis: s.ptrs.map(p => [get(p + "/ci_low"), get(p + "/ci_high")]),
      })),
    },
    options: baseOptions({
      indexAxis: "y",
      scales: { x: { stacked: true, min: 0, max: 1, ticks: { callback: pctTick } }, y: { stacked: true, grid: { display: false } } },
      plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${fmtCI(ctx.raw, ctx.dataset.cis[ctx.dataIndex], FMT.pct1)}` } } },
    }),
  };
}
const policyColors = () => [0, 1, 2, 3, 4].map(k => css(`--p${k}`));

function buildPolicy() {
  const box = document.getElementById("panels-policy");
  document.getElementById("policy-scale").textContent =
    "Policy scale: 0 prohibited · 1 limited use · 2 permitted with disclosure · 3 encouraged · 4 integrated / required. " +
    "Rows with a blank policy are excluded.";
  const levels = D.descriptives.courses.level_order;
  const levelLabels = ["Intro", "Intermediate", "Upper", "Graduate"];

  // by level
  const lv = policyShares("level", levels);
  const assocLevel = find("association", "associations", { col: "level" });
  const intro0 = find("descriptives", "policy", { by: "level", group: "intro", category: "0" });
  const upper0 = find("descriptives", "policy", { by: "level", group: "upper", category: "0" });
  panel(box, {
    id: "level", title: "Policy distribution by course level", size: "short",
    takeaway: `Intro courses prohibit AI far more often than upper-level courses (${num(intro0 + "/estimate", "pct0")} vs ${num(upper0 + "/estimate", "pct0")} of course-terms).`,
    canvases: [{ id: "c-level" }], sources: ["descriptives", "association"],
    note: `Association of policy with level: Cramér's V ${num(assocLevel + "/cramers_v", "f2")} (95% cluster-bootstrap CI ${num(assocLevel + "/cramers_v_ci/0", "f2")}–${num(assocLevel + "/cramers_v_ci/1", "f2")}, the main inference). ` +
          `The chi-square p-value (${num(assocLevel + "/p_value_naive", "p3")}) is naive: it treats course-terms as independent.`,
    table: tableHTML("Share of course-terms at each policy level (95% CI)", ["Level", ...POLICY_LABELS],
      levels.map((g, i) => [levelLabels[i], ...lv.map(s => shareCell(s.ptrs[i]))])),
  });
  makeChart("c-level", stackedConfig(levelLabels, lv, policyColors()));

  // SE vs non-SE
  const se = policyShares("is_se_label", ["SE", "non-SE"]);
  const seM = find("descriptives", "policy", { by: "is_se_label", group: "SE", category: "mean" });
  const nonM = find("descriptives", "policy", { by: "is_se_label", group: "non-SE", category: "mean" });
  const assocSE = find("association", "associations", { col: "is_se_label" });
  panel(box, {
    id: "se", title: "Software engineering vs other courses", size: "short",
    takeaway: `SE courses are more permissive: mean policy ${num(seM + "/estimate", "f2")} vs ${num(nonM + "/estimate", "f2")} for non-SE courses.`,
    canvases: [{ id: "c-se" }], sources: ["descriptives", "association"],
    note: `Cramér's V ${num(assocSE + "/cramers_v", "f2")} (95% cluster-bootstrap CI ${num(assocSE + "/cramers_v_ci/0", "f2")}–${num(assocSE + "/cramers_v_ci/1", "f2")}); naive chi-square p ${num(assocSE + "/p_value_naive", "p3")}. ` +
          `The regression view shows this holds within each level.`,
    table: tableHTML("Policy shares and mean (95% CI)", ["Group", ...POLICY_LABELS, "Mean"],
      [["SE", 0, seM], ["non-SE", 1, nonM]].map(([g, i, m]) => [g, ...se.map(s => shareCell(s.ptrs[i])), shareCell(m, "f2")])),
  });
  makeChart("c-se", stackedConfig(["SE", "Non-SE"], se, policyColors()));

  // trend by term
  const terms = D.descriptives.courses.term_order;
  const tm = terms.map(t => find("descriptives", "policy", { by: "term", group: t, category: "mean" }));
  panel(box, {
    id: "term", title: "Trend by term",
    takeaway: `Policies loosen every term: mean policy rises from ${num(tm[0] + "/estimate", "f2")} in ${terms[0]} to ${num(tm[tm.length - 1] + "/estimate", "f2")} in ${terms[terms.length - 1]}.`,
    canvases: [{ id: "c-term" }], sources: ["descriptives"],
    table: tableHTML("Mean policy by term (95% CI)", ["Term", "Mean", "Course-terms", "Institutions"],
      terms.map((t, i) => [t, shareCell(tm[i], "f2"), num(tm[i] + "/n_rows", "int"), num(tm[i] + "/n_clusters", "int")])),
  });
  const s1 = css("--s1");
  makeChart("c-term", {
    type: "line",
    data: { labels: terms, datasets: [
      { label: "95% CI upper", data: tm.map(p => get(p + "/ci_high")), srcs: tm.map(p => p + "/ci_high"),
        borderWidth: 0, pointRadius: 0, fill: false, band: true },
      { label: "95% CI", data: tm.map(p => get(p + "/ci_low")), srcs: tm.map(p => p + "/ci_low"),
        borderWidth: 0, pointRadius: 0, fill: "-1", backgroundColor: s1 + "33", band: true },
      { label: "Mean policy", data: tm.map(p => get(p + "/estimate")), srcs: tm.map(p => p + "/estimate"),
        borderColor: s1, backgroundColor: s1, borderWidth: 2, pointRadius: 4, pointHoverRadius: 6,
        cis: tm.map(p => [get(p + "/ci_low"), get(p + "/ci_high")]) },
    ] },
    options: baseOptions({
      interaction: { mode: "index", intersect: false },
      scales: { y: { min: 0, max: 4, title: { display: true, text: "Mean policy (0–4)", color: css("--ink-2") } } },
      plugins: {
        legend: { display: false },
        tooltip: { filter: i => !i.dataset.band, callbacks: { label: ctx => `Mean policy: ${fmtCI(ctx.raw, ctx.dataset.cis[ctx.dataIndex], FMT.f2)}` } },
      },
    }),
  });

  // census region
  const rp = REGIONS.map(r => find("descriptives", "policy", { by: "census_region", group: r, category: "mean" }));
  const rs = REGIONS.map(r => find("descriptives", "statement_codes", { by: "census_region", group: r, category: "mean" }));
  const overlap = ptrs => Math.max(...ptrs.map(p => get(p + "/ci_low"))) <= Math.min(...ptrs.map(p => get(p + "/ci_high")));
  const lo = rp.reduce((a, p) => (get(p + "/estimate") < get(a + "/estimate") ? p : a));
  const hi = rp.reduce((a, p) => (get(p + "/estimate") > get(a + "/estimate") ? p : a));
  panel(box, {
    id: "region", title: "Census-region comparison", size: "short",
    takeaway: `Regions differ little: mean policy runs from ${num(lo + "/estimate", "f2")} (${get(lo + "/group")}) to ${num(hi + "/estimate", "f2")} (${get(hi + "/group")}), ` +
      (overlap(rp) ? "and every region's 95% CI overlaps the others." : "though not every region's 95% CI overlaps the others."),
    canvases: [{ id: "c-region-policy", title: "Mean course policy (0–4)" }, { id: "c-region-stance", title: "Mean coded stance (−2 to +2)" }],
    sources: ["descriptives"],
    note: "Regions, not states: with about three synthetic institutions per state, state averages are mostly noise.",
    table: tableHTML("Mean policy and mean coded stance by census region (95% CI)", ["Region", "Mean policy", "Course-terms", "Mean stance", "Statements", "Institutions"],
      REGIONS.map((r, i) => [r, shareCell(rp[i], "f2"), num(rp[i] + "/n_rows", "int"), shareCell(rs[i], "f2"), num(rs[i] + "/n_rows", "int"), num(rp[i] + "/n_clusters", "int")])),
  });
  const meanBars = (ptrs, color, min, max, title) => ({
    type: "bar",
    data: { labels: REGIONS, datasets: [{ label: title, data: ptrs.map(p => get(p + "/estimate")), srcs: ptrs.map(p => p + "/estimate"),
      ci: ptrs.map(p => [get(p + "/ci_low"), get(p + "/ci_high")]), backgroundColor: color, borderRadius: 4, barPercentage: 0.6 }] },
    options: baseOptions({
      indexAxis: "y", scales: { x: { min, max }, y: { grid: { display: false } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${title}: ${fmtCI(ctx.raw, ctx.dataset.ci[ctx.dataIndex], FMT.f2)}` } } },
    }),
    plugins: [ciPlugin],
  });
  makeChart("c-region-policy", meanBars(rp, css("--s1"), 0, 4, "Mean policy"));
  makeChart("c-region-stance", meanBars(rs, css("--s1"), -2, 2, "Mean stance"));
}

// ---------- view: uses & assessment ----------
function buildUses() {
  const box = document.getElementById("panels-uses");
  const levels = D.descriptives.courses.level_order;
  const levelLabels = ["Intro", "Intermediate", "Upper", "Graduate"];
  const cell = {};
  USES.forEach(([u]) => levels.forEach(l => { cell[u + l] = find("allowed_uses", "uses", { by: "level", group: l, outcome: u }); }));
  const gap = find("allowed_uses", "intro_learning_vs_generation_gap", { minuend: "explanation" });
  const gapD = find("allowed_uses", "intro_learning_vs_generation_gap", { minuend: "debugging" });
  panel(box, {
    id: "heat", title: "Allowed uses by course level",
    takeaway: `Intro courses allow AI for learning, not for writing code: explanation is allowed ${num(gap + "/estimate", "pp0")} percentage points more often than code generation (95% CI ${num(gap + "/ci_low", "pp0")}–${num(gap + "/ci_high", "pp0")}).`,
    canvases: [{ id: "c-heat" }], sources: ["allowed_uses"],
    note: `Share of course-terms that allow each use, among those with policy ≥ 1 (${num("allowed_uses.json#/n_rows", "int")} rows; uses are empty at policy 0 by design). ` +
          `Debugging vs code generation in intro: +${num(gapD + "/estimate", "pp0")} points (95% CI ${num(gapD + "/ci_low", "pp0")}–${num(gapD + "/ci_high", "pp0")}).`,
    table: tableHTML("Share allowing each use (95% CI)", ["Use", ...levelLabels], USES.map(([u, ul]) => [ul, ...levels.map(l => shareCell(cell[u + l], "pct0"))])),
  });
  const pts = [], srcs = [];
  USES.forEach(([u, ul]) => levelLabels.forEach((ll, j) => {
    const p = cell[u + levels[j]] + "/estimate";
    pts.push({ x: ll, y: ul, v: get(p) }); srcs.push({ v: p });
  }));
  makeChart("c-heat", {
    type: "matrix",
    data: { datasets: [{ label: "Share allowing the use", data: pts, srcs,
      backgroundColor: c => seqStep(c.raw ? c.raw.v : 0).fill, borderColor: css("--surface"), borderWidth: 2,
      width: ({ chart }) => (chart.chartArea || {}).width / levelLabels.length - 2,
      height: ({ chart }) => (chart.chartArea || {}).height / USES.length - 2 }] },
    options: baseOptions({
      scales: {
        x: { type: "category", labels: levelLabels, offset: true, grid: { display: false } },
        y: { type: "category", labels: USES.map(u => u[1]), offset: true, grid: { display: false } },
      },
      plugins: { legend: { display: false }, tooltip: { callbacks: { title: () => "", label: ctx => `${ctx.raw.y}, ${ctx.raw.x}: ${FMT.pct0(ctx.raw.v)} allow` } } },
    }),
    plugins: [cellLabelPlugin],
  });

  // assessment by policy
  const pols = ["0", "1", "2", "3", "4"];
  const series = ASSESS.map(([a, al]) => ({ label: al, ptrs: pols.map(g => find("assessment", "shares", { by: "policy", group: g, category: a })) }));
  const ex0 = find("assessment", "shares", { by: "policy", group: "0", category: "in_class_exams" });
  const ex4 = find("assessment", "shares", { by: "policy", group: "4", category: "in_class_exams" });
  const assoc = find("assessment", "association", { col: "policy" });
  panel(box, {
    id: "assess", title: "Assessment changes by policy level",
    takeaway: `Restrictive courses lean on in-class exams: ${num(ex0 + "/estimate", "pct0")} of prohibiting course-terms use them, against ${num(ex4 + "/estimate", "pct0")} at policy 4.`,
    canvases: [{ id: "c-assess" }], sources: ["assessment"],
    note: `Cramér's V ${num(assoc + "/cramers_v", "f2")} (95% cluster-bootstrap CI ${num(assoc + "/cramers_v_ci/0", "f2")}–${num(assoc + "/cramers_v_ci/1", "f2")}); naive chi-square p ${num(assoc + "/p_value_naive", "p3")}.`,
    table: tableHTML("Share of course-terms with each assessment change (95% CI)", ["Policy", ...ASSESS.map(a => a[1])],
      pols.map((g, i) => [POLICY_LABELS[i], ...series.map(s => shareCell(s.ptrs[i], "pct0"))])),
  });
  makeChart("c-assess", stackedConfig(POLICY_LABELS, series, [1, 2, 3, 4, 5].map(k => css(`--s${k}`))));
}

// ---------- view: statements ----------
function buildStatements() {
  const box = document.getElementById("panels-statements");
  const st = ["-2", "-1", "0", "1", "2"].map(k => find("descriptives", "statement_codes", { by: "all", outcome: "coded_stance", category: k }));
  const th = THEMES.map(([t]) => find("descriptives", "statement_codes", { by: "all", outcome: "coded_" + t, category: "True" }));
  const top = th.reduce((a, p) => (get(p + "/estimate") > get(a + "/estimate") ? p : a));
  const topName = THEMES[th.indexOf(top)][1];
  const mean = find("descriptives", "statement_codes", { by: "all", category: "mean" });
  panel(box, {
    id: "stance", title: "Stance and theme prevalence",
    takeaway: `${topName} is the most common theme (${num(top + "/estimate", "pct0")} of statements), and the average coded stance is ${num(mean + "/estimate", "f2")} on a −2 to +2 scale.`,
    canvases: [{ id: "c-stance", title: "Coded stance (share of statements)" }, { id: "c-themes", title: "Theme mentioned (share of statements)" }],
    sources: ["descriptives"],
    note: `All ${num("descriptives.json#/statements/n", "int")} statements, as labelled by the rule-based coder. By-year and by-Carnegie breakdowns are in descriptives.json.`,
    table: tableHTML("Share of statements (95% CI)", ["Label", "Share", "Statements"],
      [...st.map((p, i) => [STANCE_LABELS[["-2", "-1", "0", "1", "2"][i]], shareCell(p), num(p + "/n_rows", "int")]),
       ...th.map((p, i) => [`Mentions ${THEMES[i][1].toLowerCase()}`, shareCell(p), num(p + "/n_rows", "int")])]),
  });
  const shareBars = (labels, ptrs, title) => ({
    type: "bar",
    data: { labels, datasets: [{ label: title, data: ptrs.map(p => get(p + "/estimate")), srcs: ptrs.map(p => p + "/estimate"),
      ci: ptrs.map(p => [get(p + "/ci_low"), get(p + "/ci_high")]), backgroundColor: css("--s1"), borderRadius: 4, barPercentage: 0.7 }] },
    options: baseOptions({
      scales: { y: { min: 0, ticks: { callback: pctTick } }, x: { grid: { display: false } } },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => fmtCI(ctx.raw, ctx.dataset.ci[ctx.dataIndex], FMT.pct1) } } },
    }),
    plugins: [ciPlugin],
  });
  makeChart("c-stance", shareBars(["−2", "−1", "0", "+1", "+2"], st, "Coded stance"));
  makeChart("c-themes", shareBars(THEMES.map(t => t[1]), th, "Theme"));

  // rhetoric vs practice
  const R = D.rhetoric;
  const topIds = new Set(R.top_decile.map(r => r.inst_id));
  const name = id => (D.institutions.institutions.find(i => i.inst_id === id) || {}).name || id;
  const idx = R.institutions.map((r, i) => i);
  const rest = idx.filter(i => !topIds.has(R.institutions[i].inst_id)), flagged = idx.filter(i => topIds.has(R.institutions[i].inst_id));
  const r = "rhetoric.json#/correlation";
  const weak = Math.abs(R.correlation.pearson_r) < 0.2;
  panel(box, {
    id: "rhetoric", title: "Rhetoric vs practice", size: "tall",
    takeaway: `Across ${num("rhetoric.json#/n_institutions", "int")} institutions, what a department says ${weak ? "barely predicts" : "tracks"} what its courses allow ` +
      `(r = ${num(r + "/pearson_r", "f2")}, 95% CI ${num(r + "/ci/0", "f2")} to ${num(r + "/ci/1", "f2")}); the ${num("rhetoric.json#/top_decile_k", "int")} largest mismatches are highlighted. Select a dot to open that institution.`,
    canvases: [{ id: "c-scatter" }], sources: ["rhetoric"],
    note: `Gap = ${esc(R.gap_definition)}. One dot per institution with at least one statement and one known-policy course.`,
    table: tableHTML("Largest rhetoric–practice gaps (top decile)", ["Institution", "Mean stance", "Mean policy", "Gap", "Direction"],
      R.top_decile.map((t, i) => [`<button type="button" class="linkbtn" data-inst="${t.inst_id}">${esc(name(t.inst_id))}</button>`,
        num(`rhetoric.json#/top_decile/${i}/mean_stance`, "f2"), num(`rhetoric.json#/top_decile/${i}/mean_policy`, "f2"),
        num(`rhetoric.json#/top_decile/${i}/gap`, "f2"), esc(t.direction)])),
  });
  document.querySelectorAll("#panel-rhetoric [data-inst]").forEach(b => b.addEventListener("click", () => openInstitution(b.dataset.inst)));
  const ds = (ids, label, color, radius) => ({
    label, data: ids.map(i => ({ x: R.institutions[i].mean_stance, y: R.institutions[i].mean_policy, inst_id: R.institutions[i].inst_id })),
    srcs: ids.map(i => ({ x: `rhetoric.json#/institutions/${i}/mean_stance`, y: `rhetoric.json#/institutions/${i}/mean_policy` })),
    backgroundColor: color + "b3", borderColor: css("--surface"), borderWidth: 1, pointRadius: radius, pointHoverRadius: radius + 3, pointHitRadius: 8,
  });
  makeChart("c-scatter", {
    type: "scatter",
    data: { datasets: [ds(rest, "Other institutions", css("--s1"), 4), ds(flagged, "Top-decile gap", css("--s2"), 6)] },
    options: baseOptions({
      scales: {
        x: { min: -2.2, max: 2.2, title: { display: true, text: "Mean coded stance of statements (−2 to +2)", color: css("--ink-2") } },
        y: { min: 0, max: 4, title: { display: true, text: "Mean course policy (0–4)", color: css("--ink-2") } },
      },
      onHover: (e, els) => { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
      onClick: (e, els) => { if (els.length) { const p = els[0]; openInstitution(charts["c-scatter"].data.datasets[p.datasetIndex].data[p.index].inst_id); } },
      plugins: { tooltip: { callbacks: { label: ctx => `${name(ctx.raw.inst_id)}: stance ${FMT.f2(ctx.raw.x)}, policy ${FMT.f2(ctx.raw.y)}` } } },
    }),
  });
}

// ---------- view: regression ----------
function buildModel() {
  const box = document.getElementById("panels-model");
  const R = D.regression;
  const order = ["intermediate", "upper", "graduate", "is_se", "term_index", "private", "R2", "Masters", "Baccalaureate"];
  const ptr = order.map(t => find("regression", "coefficients", { term: t }));
  const priv = find("regression", "coefficients", { term: "private" });
  const sig = get(priv + "/p_clustered") < 0.05;
  const bac = find("regression", "coefficients", { term: "Baccalaureate" });
  panel(box, {
    id: "coef", title: "Ordinal regression coefficients", size: "tall",
    takeaway: `Course level, SE and term drive policy; public vs private ${sig ? "also matters" : "does not matter"} once standard errors are clustered by institution ` +
      `(p = ${num(priv + "/p_clustered", "p3")} clustered vs ${num(priv + "/p_naive", "p3")} naive).`,
    canvases: [{ id: "c-coef" }], sources: ["regression"],
    note: `Log-odds of a more permissive policy, ${esc(R.model.split(":")[0])}; n = ${num("regression.json#/n_used", "int")} course-terms in ${num("regression.json#/n_clusters", "int")} institutions. ` +
      `Thick bars: 95% CI from ${esc(R.inference.main)} (main inference). Thin grey bars: naive CI treating rows as independent. ` +
      `Baccalaureate shows why this matters: naive p = ${num(bac + "/p_naive", "p3")}, clustered p = ${num(bac + "/p_clustered", "p3")}.`,
    table: tableHTML("Coefficients with clustered and naive inference", ["Term", "Coef", "Clustered 95% CI", "p (clustered)", "Naive 95% CI", "p (naive)"],
      ptr.map((p, i) => [COEF_LABELS[order[i]], num(p + "/coef", "f2"),
        `${num(p + "/ci_clustered/0", "f2")} to ${num(p + "/ci_clustered/1", "f2")}`, num(p + "/p_clustered", "p3"),
        `${num(p + "/ci_naive/0", "f2")} to ${num(p + "/ci_naive/1", "f2")}`, num(p + "/p_naive", "p3")])),
  });
  makeChart("c-coef", {
    type: "bar",
    data: { labels: order.map(t => COEF_LABELS[t]), datasets: [
      { type: "line", label: "Coefficient", data: ptr.map(p => get(p + "/coef")), srcs: ptr.map(p => p + "/coef"),
        showLine: false, pointRadius: 5, pointHoverRadius: 7, backgroundColor: css("--ink"), borderColor: css("--surface"), borderWidth: 1.5, order: 0 },
      { label: "95% CI, clustered by institution", data: ptr.map(p => get(p + "/ci_clustered")), srcs: ptr.map(p => [p + "/ci_clustered/0", p + "/ci_clustered/1"]),
        backgroundColor: css("--s1"), borderRadius: 4, barThickness: 10, grouped: false, order: 2 },
      { label: "95% CI, naive", data: ptr.map(p => get(p + "/ci_naive")), srcs: ptr.map(p => [p + "/ci_naive/0", p + "/ci_naive/1"]),
        backgroundColor: css("--naive"), borderRadius: 2, barThickness: 3, grouped: false, order: 1 },
    ] },
    options: baseOptions({
      indexAxis: "y",
      interaction: { mode: "index", intersect: false, axis: "y" },
      scales: { x: { title: { display: true, text: "Coefficient (log-odds); 0 = no effect", color: css("--ink-2") },
                     grid: { color: c => (c.tick.value === 0 ? css("--axis") : css("--grid")), lineWidth: c => (c.tick.value === 0 ? 2 : 1) } },
                y: { grid: { display: false } } },
      plugins: { tooltip: { callbacks: { label: ctx => Array.isArray(ctx.raw) ? `${ctx.dataset.label}: ${FMT.f2(ctx.raw[0])} to ${FMT.f2(ctx.raw[1])}` : `Coefficient: ${FMT.f2(ctx.raw)}` } } },
    }),
  });
}

// ---------- view: coder accuracy ----------
function buildCoder() {
  const box = document.getElementById("panels-coder");
  const sets = [["heldout", "All held-out"], ["heldout_without_reserved_phrasings", "Phrasings seen in dev"], ["heldout_with_reserved_phrasings", "Unseen (reserved) phrasings"]];
  const cats = [["stance", "Stance (macro-F1)"], ...THEMES.map(([t, l]) => [t, l + " (F1)"])];
  const p = (set, cat) => (cat === "stance" ? `coder_eval.json#/${set}/stance/macro_f1` : `coder_eval.json#/${set}/labels/${cat}/f1`);
  panel(box, {
    id: "f1", title: "Rule-based coder vs truth, held-out statements",
    takeaway: `The coder reaches macro-F1 ${num("coder_eval.json#/heldout/macro_f1", "f3")} on held-out statements (target ${num("coder_eval.json#/target_macro_f1", "f2")}), ` +
      `but falls to ${num("coder_eval.json#/heldout_with_reserved_phrasings/macro_f1", "f3")} on phrasings it never saw while its rules were written.`,
    canvases: [{ id: "c-f1" }], sources: ["coder_eval"],
    note: `Held-out n = ${num("coder_eval.json#/heldout/n", "int")} statements; rules frozen at commit <code>${esc(D.coder_eval.rules_frozen_commit)}</code>. ` +
      (THEMES.every(([t]) => ["heldout", "heldout_with_reserved_phrasings", "heldout_without_reserved_phrasings"].every(set => D.coder_eval[set].labels[t].precision === 1))
        ? `Theme precision is ${num("coder_eval.json#/heldout/labels/mentions_integrity/precision", "f2")} for every theme and set: the coder misses mentions rather than inventing them. `
        : "") +
      `Macro-F1 = ${esc(D.coder_eval.macro_f1_definition)}.`,
    table: tableHTML("F1 by label and statement set", ["Label", ...sets.map(s => s[1])],
      [...cats.map(([c, cl]) => [cl, ...sets.map(([s]) => num(p(s, c), "f3"))]),
       ["Macro-F1", ...sets.map(([s]) => num(`coder_eval.json#/${s}/macro_f1`, "f3"))],
       ["Statements", ...sets.map(([s]) => num(`coder_eval.json#/${s}/n`, "int"))]]),
  });
  makeChart("c-f1", {
    type: "bar",
    data: { labels: cats.map(c => c[1]), datasets: [
      ...sets.map(([s, sl], k) => ({ label: sl, data: cats.map(([c]) => get(p(s, c))), srcs: cats.map(([c]) => p(s, c)),
        backgroundColor: css(`--s${k + 1}`), borderColor: css("--surface"), borderWidth: 2, borderRadius: 4, order: 1 })),
      { type: "line", label: "Target macro-F1", data: cats.map(() => D.coder_eval.target_macro_f1), srcs: cats.map(() => "coder_eval.json#/target_macro_f1"),
        borderColor: css("--ink-2"), borderDash: [5, 4], borderWidth: 1.5, pointRadius: 0, order: 0 },
    ] },
    options: baseOptions({ scales: { y: { min: 0, max: 1 }, x: { grid: { display: false } } },
      plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: ${FMT.f3(ctx.raw)}` } } } }),
  });

  const K = D.kappa;
  const codes = [["stance", "Stance"], ...THEMES];
  const comps = [["aayush_vs_truth", K.comparison_labels.aayush_vs_truth], ["aayush_vs_coder", K.comparison_labels.aayush_vs_coder]];
  panel(box, {
    id: "kappa", title: "Hand-coded sample: Cohen's kappa", size: "short",
    takeaway: `On ${num("kappa.json#/n", "int")} hand-coded statements, Aayush agrees with the truth (stance κ = ${num("kappa.json#/aayush_vs_truth/stance", "f2")}) ` +
      `more than with the coder (κ = ${num("kappa.json#/aayush_vs_coder/stance", "f2")}): the codebook is clear, and most disagreement comes from the coder.`,
    canvases: [{ id: "c-kappa" }], sources: ["kappa"],
    note: `Unweighted Cohen's kappa per code; coded by ${esc(K.coder_by)} from the codebook, held-out statements only.`,
    table: tableHTML("Cohen's kappa by code", ["Code", ...comps.map(c => esc(c[1]))],
      codes.map(([c, cl]) => [cl, ...comps.map(([k]) => num(`kappa.json#/${k}/${c}`, "f2"))])),
  });
  makeChart("c-kappa", {
    type: "bar",
    data: { labels: codes.map(c => c[1]), datasets: comps.map(([k, kl], i) => ({
      label: kl, data: codes.map(([c]) => K[k][c]), srcs: codes.map(([c]) => `kappa.json#/${k}/${c}`),
      backgroundColor: css(`--s${i + 1}`), borderColor: css("--surface"), borderWidth: 2, borderRadius: 4 })) },
    options: baseOptions({ scales: { y: { min: 0, max: 1, title: { display: true, text: "Cohen's κ", color: css("--ink-2") } }, x: { grid: { display: false } } },
      plugins: { tooltip: { callbacks: { label: ctx => `${ctx.dataset.label}: κ = ${FMT.f2(ctx.raw)}` } } } }),
  });
}

// ---------- statements (explorer + drilldown share the card renderer) ----------
function stmtCard(s, i, q) {
  let text = esc(s.text);
  if (q) text = text.replace(new RegExp(q.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), m => `<mark>${m}</mark>`);
  const inst = D.instById[s.inst_id];
  const theme = ([t, l]) => s[`coded_${t}`]
    ? `<span class="chip">${l} <code>${s[`coded_${t}_rules`].map(esc).join(", ")}</code></span>`
    : `<span class="chip off">no ${l.toLowerCase()}</span>`;
  return `<li class="stmt" data-stmt="${s.stmt_id}">
    <div class="meta"><span>${esc(s.stmt_id)}</span><button type="button" class="linkbtn" data-inst="${s.inst_id}">${esc(inst ? inst.name : s.inst_id)}</button>
      <span>${esc(s.pub_type.replace(/_/g, " "))}</span><span>${esc(s.pub_date)}</span></div>
    <p class="text">${text}</p>
    <div class="chips"><span class="chip">Stance <span class="num" data-src="statements.json#/statements/${i}/coded_stance" data-fmt="int">${s.coded_stance}</span> <code>${esc(s.coded_stance_rule)}</code></span>
      ${THEMES.map(theme).join("")}</div></li>`;
}
function bindInstLinks(root) {
  root.querySelectorAll("[data-inst]").forEach(b => b.addEventListener("click", () => openInstitution(b.dataset.inst)));
}

const EX = { page: 30, shown: 30 };
function buildExplorer() {
  const S = D.statements.statements;
  const opt = (id, items) => { document.getElementById(id).innerHTML = items.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join(""); };
  opt("f-stance", [["", "Any"], ...["-2", "-1", "0", "1", "2"].map(k => [k, STANCE_LABELS[k]])]);
  opt("f-theme", [["", "Any"], ...THEMES.map(([t, l]) => [t, l]), ["none", "No theme"]]);
  opt("f-type", [["", "Any"], ...[...new Set(S.map(s => s.pub_type))].sort().map(t => [t, t.replace(/_/g, " ")])]);
  opt("f-year", [["", "Any"], ...[...new Set(S.map(s => s.year))].sort().map(y => [y, y])]);
  const form = document.getElementById("explorer-form");
  form.addEventListener("input", () => { EX.shown = EX.page; renderExplorer(); });
  document.getElementById("f-reset").addEventListener("click", () => { form.reset(); EX.shown = EX.page; renderExplorer(); });
  document.getElementById("explorer-more").addEventListener("click", () => { EX.shown += EX.page; renderExplorer(); });
  renderExplorer();
}
function renderExplorer() {
  const S = D.statements.statements;
  const q = document.getElementById("f-q").value.trim();
  const stance = document.getElementById("f-stance").value, theme = document.getElementById("f-theme").value;
  const type = document.getElementById("f-type").value, year = document.getElementById("f-year").value;
  const ql = q.toLowerCase();
  const hits = [];
  S.forEach((s, i) => {
    if (ql && !s.text.toLowerCase().includes(ql)) return;
    if (stance !== "" && String(s.coded_stance) !== stance) return;
    if (theme === "none" && THEMES.some(([t]) => s[`coded_${t}`])) return;
    if (theme && theme !== "none" && !s[`coded_${theme}`]) return;
    if (type && s.pub_type !== type) return;
    if (year && s.year !== year) return;
    hits.push(i);
  });
  const shown = hits.slice(0, EX.shown);
  // counts describe the current filter, not a result: tagged data-derived (checked by the UI test against the rows)
  document.getElementById("explorer-count").innerHTML =
    `Showing <span data-derived="shown">${shown.length}</span> of <span data-derived="matches">${hits.length}</span> matching statements ` +
    `(${num("statements.json#/n", "int")} in total).`;
  const list = document.getElementById("explorer-list");
  list.innerHTML = shown.map(i => stmtCard(S[i], i, q)).join("");
  bindInstLinks(list);
  document.getElementById("explorer-more").hidden = shown.length >= hits.length;
}

// ---------- drilldown ----------
function buildDrilldown() {
  const pick = document.getElementById("inst-pick");
  const insts = [...D.institutions.institutions].sort((a, b) => a.name.localeCompare(b.name));
  pick.innerHTML = insts.map(i => `<option value="${i.inst_id}">${esc(i.name)} (${i.state})</option>`).join("");
  pick.addEventListener("change", () => openInstitution(pick.value));
}
function renderInstitution(id) {
  const pick = document.getElementById("inst-pick");
  const ii = D.institutions.institutions.findIndex(i => i.inst_id === id);
  if (ii < 0) { document.getElementById("inst-detail").innerHTML = `<p class="error">Unknown institution ${esc(id)}.</p>`; return; }
  pick.value = id;
  const inst = D.institutions.institutions[ii], ip = `institutions.json#/institutions/${ii}`;
  const ri = D.rhetoric.institutions.findIndex(r => r.inst_id === id);
  const ti = D.rhetoric.top_decile.findIndex(r => r.inst_id === id);
  const rp = `rhetoric.json#/institutions/${ri}`;
  const head = [
    ["Location", `${esc(inst.state)} · ${esc(inst.census_region)}`], ["Control", esc(inst.control)], ["Carnegie", esc(inst.carnegie)],
    ["CS enrollment", num(ip + "/cs_enrollment", "int")],
    ...(ri >= 0 ? [["Mean coded stance", num(rp + "/mean_stance", "f2")], ["Mean course policy", num(rp + "/mean_policy", "f2")],
                   ["Rhetoric–practice gap", `${num(rp + "/gap", "f2")} ${ti >= 0 ? `<span class="flag">top decile: ${esc(D.rhetoric.top_decile[ti].direction)}</span>` : ""}`]]
                 : [["Rhetoric–practice gap", "not computed (no statement or no known-policy course)"]]),
  ];
  const terms = D.descriptives.courses.term_order;
  const C = D.courses.courses;
  const byCourse = new Map();
  C.forEach((c, i) => { if (c.inst_id === id) { if (!byCourse.has(c.course_id)) byCourse.set(c.course_id, { c, terms: {} }); byCourse.get(c.course_id).terms[c.term] = i; } });
  const pcolor = k => `var(--p${k})`;
  const rows = [...byCourse.values()].map(({ c, terms: t }) => `<tr><th scope="row">${esc(c.code)} <span class="fine">${esc(c.title)}</span></th>
      <td>${esc(c.level)}${c.is_se ? " · SE" : ""}</td>
      ${terms.map(term => {
        if (!(term in t)) return `<td class="pol missing" title="not offered">·</td>`;
        const i = t[term], v = C[i].policy;
        if (v === null) return `<td class="pol missing" title="policy not stated">n/a</td>`;
        const uses = C[i].allowed_uses.join(", ") || "none";
        return `<td class="pol" title="${esc(POLICY_LABELS[v])}; uses: ${esc(uses)}; assessment: ${esc(C[i].assessment_adaptation)}"><span class="swatch" style="background:${pcolor(v)}"></span><span class="num" data-src="courses.json#/courses/${i}/policy" data-fmt="int">${v}</span></td>`;
      }).join("")}</tr>`).join("");
  const S = D.statements.statements;
  const stmts = S.map((s, i) => [s, i]).filter(([s]) => s.inst_id === id);
  document.getElementById("inst-detail").innerHTML = `
    <h3 id="inst-name">${esc(inst.name)}</h3>
    <div class="inst-head">${head.map(([l, v]) => `<div><span class="label">${l}</span>${v}</div>`).join("")}</div>
    ${ri >= 0 ? `<p class="fine" id="gap-caveat"><strong>Read the statements before trusting the gap.</strong> Stance comes from the rule-based coder, so a large gap can be a coding error rather than a real mismatch. ` +
      `For example, a negation such as “far from banning chatbots” is coded as prohibitive. See the known limits in <code>docs/methods.md</code>.</p>` : ""}
    <div class="cols">
      <div class="panel"><h3>Course policies by term</h3>
        <p class="fine">0 prohibited … 4 integrated / required. “n/a” = policy not stated; “·” = not offered that term. Hover a cell for uses and assessment.</p>
        <div class="table-wrap"><table><caption>Course policies (source: <a href="${DATA_DIR}courses.json">courses.json</a>)</caption>
          <thead><tr><th scope="col">Course</th><th scope="col">Level</th>${terms.map(t => `<th scope="col" class="n">${t}</th>`).join("")}</tr></thead>
          <tbody>${rows || `<tr><td colspan="${terms.length + 2}">No courses.</td></tr>`}</tbody></table></div></div>
      <div class="panel"><h3>Official statements (${stmts.length})</h3>
        <p class="fine">Labels are the coder's. Source: <a href="${DATA_DIR}statements.json">statements.json</a>.</p>
        ${stmts.length ? `<ol class="stmts">${stmts.map(([s, i]) => stmtCard(s, i, "")).join("")}</ol>` : "<p>This institution published no statements.</p>"}</div>
    </div>`;
  bindInstLinks(document.getElementById("inst-detail"));
}
function openInstitution(id) { location.hash = `view=drilldown&inst=${encodeURIComponent(id)}`; }

// ---------- routing, tabs, theme ----------
const BUILDERS = { summary: buildSummary, policy: buildPolicy, uses: buildUses, statements: buildStatements,
                   model: buildModel, coder: buildCoder, explorer: buildExplorer, drilldown: buildDrilldown };
const CHART_VIEWS = ["policy", "uses", "statements", "model", "coder"];
function parseHash() {
  const h = new URLSearchParams(location.hash.replace(/^#/, ""));
  const view = BUILDERS[h.get("view")] ? h.get("view") : "summary";
  return { view, inst: h.get("inst") };
}
function show(view, inst) {
  document.querySelectorAll('[role="tab"]').forEach(t => {
    const on = t.dataset.view === view;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll('[role="tabpanel"]').forEach(p => { p.hidden = p.id !== `view-${view}`; });
  if (!builtViews.has(view)) { BUILDERS[view](); builtViews.add(view); }
  if (view === "drilldown") renderInstitution(inst || D.rhetoric.top_decile[0].inst_id);
}
function route() {
  const { view, inst } = parseHash();
  try { show(view, inst); } catch (e) { fail(e); }
}
function setupTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  tabs.forEach((t, i) => {
    t.addEventListener("click", () => { location.hash = `view=${t.dataset.view}`; });
    t.addEventListener("keydown", e => {
      const k = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (k === undefined) return;
      e.preventDefault();
      const next = tabs[(k + tabs.length) % tabs.length];
      next.focus(); location.hash = `view=${next.dataset.view}`;
    });
  });
}
function resolvedTheme() {
  const t = document.documentElement.dataset.theme;
  return t || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
}
function rebuildCharts() {
  document.documentElement.dataset.resolvedTheme = resolvedTheme();
  for (const v of CHART_VIEWS) {
    if (!builtViews.has(v)) continue;
    document.getElementById(`panels-${v}`).innerHTML = "";
    BUILDERS[v]();
  }
}
function setupTheme() {
  const btn = document.getElementById("theme-toggle");
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
    label(); rebuildCharts();
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", rebuildCharts);
  document.documentElement.dataset.resolvedTheme = resolvedTheme();
  label();
}
function fail(e) {
  window.__dash.errors.push(String(e));
  const el = document.getElementById("load-error");
  el.hidden = false;
  el.textContent = `Could not build the dashboard: ${e.message || e}. Serve the site/ folder over HTTP (make serve) so the JSON files can load.`;
  console.error(e);
}

async function main() {
  try {
    await Promise.all(FILES.map(async f => {
      const r = await fetch(`${DATA_DIR}${f}.json`);
      if (!r.ok) throw new Error(`${f}.json: HTTP ${r.status}`);
      D[f] = await r.json();
    }));
    for (const f of FILES) if (D[f].synthetic !== true) throw new Error(`${f}.json is not marked synthetic`);
    D.instById = Object.fromEntries(D.institutions.institutions.map(i => [i.inst_id, i]));
    if (typeof Chart === "undefined") throw new Error("Chart.js did not load (check the network)");
    Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
    Chart.defaults.color = css("--ink-2");
    setupTabs(); setupTheme();
    window.addEventListener("hashchange", route);
    route();
    window.__dash.ready = true;
  } catch (e) { fail(e); }
}
main();
