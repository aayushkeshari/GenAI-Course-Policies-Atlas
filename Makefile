# Project Makefile. Targets are named in specs/P0-instrumentation.md (INST-06); stubs are filled in by later phases.
# Paths are relative: the project directory contains spaces.

PY ?= .venv/bin/python

.PHONY: setup data analysis test report tokens timeline site serve clean

setup:  ## create the venv and install pinned deps
	python3.11 -m venv .venv && $(PY) -m pip install -q -r requirements.txt

SEED ?= 2026

data:  ## P1: generate synthetic data + ground truth into data/raw/ (deterministic for a given SEED)
	$(PY) src/data/generate.py --seed $(SEED) --out data/raw

analysis:  ## P2: clean, code, analyze -> results/ (src/analysis never reads ground truth), then evaluate (src/evaluation)
	$(PY) -m src.analysis.run
	$(PY) -m src.evaluation.run

test:  ## run pytest; tests/conftest.py writes results/tests/run-<ts>.json (INST-07)
	$(PY) -m pytest

report:  ## P3/P4: build dashboard + validation explorer data
	@echo "report: not implemented yet (P3/P4)"

tokens:  ## P6: token usage report
	@echo "tokens: not implemented yet (P6)"

timeline:  ## P5: contribution timeline
	@echo "timeline: not implemented yet (P5)"

site:  ## P7: assemble site/
	@echo "site: not implemented yet (P7)"

serve:  ## P7: serve site/ locally
	@echo "serve: not implemented yet (P7)"

clean:  ## remove caches only; never touches logs/, raw_logs/, or results/tests/ (VAL-02 keeps every run)
	rm -rf .pytest_cache .coverage htmlcov
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
