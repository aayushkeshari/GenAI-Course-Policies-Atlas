# Project Makefile. Targets are named in specs/P0-instrumentation.md (INST-06); stubs are filled in by later phases.
# Paths are relative: the project directory contains spaces.

PY ?= .venv/bin/python

.PHONY: setup data analysis test faults report tokens timeline site serve clean

setup:  ## create the venv, install pinned deps, and install Chromium for the dashboard UI tests (DASH-07)
	python3.11 -m venv .venv && $(PY) -m pip install -q -r requirements.txt
	$(PY) -m playwright install chromium

SEED ?= 2026

data:  ## P1: generate synthetic data + ground truth into data/raw/ (deterministic for a given SEED)
	$(PY) src/data/generate.py --seed $(SEED) --out data/raw

analysis:  ## P2: clean, code, analyze -> results/ (src/analysis never reads ground truth), then evaluate (src/evaluation)
	$(PY) -m src.analysis.run
	$(PY) -m src.evaluation.run

test:  ## run pytest; tests/conftest.py writes results/tests/run-<ts>.json (INST-07) and pytest-cov writes results/tests/coverage/latest.json, archived per run in results/tests/coverage/ (VAL-03)
	$(PY) -m pytest --cov=src --cov-report=json:results/tests/coverage/latest.json; s=$$?; \
	$(PY) -m src.validation.runs attach-coverage || s=1; exit $$s

faults:  ## P4 (VAL-04): inject deliberate bugs into a temp copy of the repo, run the suite, write results/faults.json
	$(PY) -m src.validation.faults

report:  ## P3/P4: build dashboard data into site/data/ and validation explorer data into site/validation/data/
	$(PY) -m src.report.build_site_data
	$(PY) -m src.report.build_validation_data

tokens:  ## P6 (TOK-02..05): one row per assistant message from raw_logs/transcripts/ + phase join + metrics -> results/tokens.json
	$(PY) -m src.tokens.build_tokens

timeline:  ## P5 (PROV-01): merge hook events, git log, progress and review logs into site/timeline/data/timeline.json (redacted, PROV-06)
	$(PY) -m src.provenance.build_timeline

site:  ## P7: assemble site/
	@echo "site: not implemented yet (P7)"

PORT ?= 8000

serve:  ## serve site/ locally at http://127.0.0.1:$(PORT)/ (minimal version added in P3 to view the dashboard; P7 may extend it)
	$(PY) -m http.server $(PORT) --bind 127.0.0.1 --directory site

clean:  ## remove caches only; never touches logs/, raw_logs/, or results/tests/ (VAL-02 keeps every run)
	rm -rf .pytest_cache .coverage htmlcov
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
