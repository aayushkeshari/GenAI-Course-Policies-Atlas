// PUB-05: render evaluation.md (an unedited copy of docs/evaluation.md) as HTML. marked parses, DOMPurify sanitizes.
"use strict";
const SRC = "evaluation.md";

function showError(msg) {
  const e = document.getElementById("load-error");
  e.textContent = msg;
  e.hidden = false;
  document.getElementById("evaluation").innerHTML = "";
}

fetch(SRC)
  .then(r => { if (!r.ok) throw new Error(`${SRC}: HTTP ${r.status}`); return r.text(); })
  .then(md => {
    if (typeof marked === "undefined" || typeof DOMPurify === "undefined") throw new Error("the Markdown libraries did not load");
    document.getElementById("evaluation").innerHTML = DOMPurify.sanitize(marked.parse(md));
  })
  .catch(err => showError(`Could not show the evaluation (${err.message}). Run make site, or read docs/evaluation.md in the repo.`));
