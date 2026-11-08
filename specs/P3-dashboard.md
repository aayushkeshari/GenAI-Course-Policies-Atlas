# P3 — Findings dashboard (site/dashboard/)

- **DASH-01** Static page that loads `site/data/*.json` (copied from results/ by `make site`).
  Chart.js pinned to an exact version via CDN. No build step.
- **DASH-02** A visible "Synthetic data — illustrative only" banner on every view.
- **DASH-03** Views: KPI summary; policy distribution by level (stacked bars); SE vs non-SE; trend by term;
  US state tile-grid map of average permissiveness (no geo library); stance and theme prevalence;
  regression coefficient plot with CIs; coder accuracy panel (ANL-03/04).
- **DASH-04** Statement explorer: full-text search plus filters by stance, theme, pub_type, and year.
  Shows coded labels next to the text so readers can judge the coder.
- **DASH-05** Each chart has a one-sentence takeaway, a "data table" toggle, and a link to its JSON source.
- **DASH-06** Color-blind-safe palette, keyboard navigable, works at 375px width, light and dark mode.
- **DASH-07** Tests: every number displayed matches results JSON; a headless browser (Playwright for Python)
  loads each view with no console errors and finds each chart canvas populated.
