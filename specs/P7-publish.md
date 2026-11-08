# P7 — Publish

- **PUB-01** `site/index.html` landing page linking Dashboard, Validation, Timeline, Tokens, Evaluation & Reflection,
  and the GitHub repo.
- **PUB-02** GitHub Actions workflow deploys site/ to GitHub Pages on push to main.
- **PUB-03** Pre-publish gate (`make prepublish`): all tests pass, redaction scan clean, link check passes,
  synthetic banner present on every data page.
- **PUB-04** README.md explains the project, how to reproduce everything (`make all`), and the live URL.
- **PUB-05** docs/evaluation.md and the reflection are rendered as a page, unedited by Claude.
