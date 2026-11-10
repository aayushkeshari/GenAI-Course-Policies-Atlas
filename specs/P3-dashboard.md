# P3 — Findings dashboard (site/dashboard/)

- **DASH-01** Static page that loads `site/data/*.json` (copied from results/ by `make site`).
  Chart.js pinned to an exact version via CDN. No build step.
- **DASH-02** A visible synthetic-data banner on every view: "Synthetic data: real university names are attached to invented
  policies and statements. Nothing here describes what these schools actually do." (wording changed by HUMAN, 2026-11-10).
- **DASH-03** Views: KPI summary; policy distribution by level (stacked bars); SE vs non-SE; trend by term;
  census-region comparison (no state map: with ~3 synthetic institutions per state, state averages are just noise);
  allowed-uses heatmap (use × course level, RQ6); assessment-changes chart by policy level (RQ7);
  rhetoric-vs-practice scatter, one dot per institution with stance on one axis and course permissiveness on the other (RQ8); stance and theme prevalence;
  regression coefficient plot with CIs; coder accuracy panel (ANL-03/04).
- **DASH-04** Statement explorer: full-text search plus filters by stance, theme, pub_type, and year.
  Shows coded labels next to the text so readers can judge the coder.
- **DASH-05** Each chart has a one-sentence takeaway, a "data table" toggle, and a link to its JSON source.
- **DASH-06** Color-blind-safe palette, keyboard navigable, works at 375px width, light and dark mode.
- **DASH-08** Institution drilldown: pick one institution and see its course policies next to its official statements,
  so you can spot departments whose rhetoric doesn't match their actual course rules. Clicking a dot in the
  rhetoric-vs-practice scatter opens that institution here.
- **DASH-07** Tests: every number displayed matches results JSON; a headless browser (Playwright for Python)
  loads each view with no console errors and finds each chart canvas populated.
