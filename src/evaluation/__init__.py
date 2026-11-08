"""Scores the analysis against the hidden truth (ANL-03, ANL-04).

This package and tests/ are the only code allowed to read the hidden truth file. All access goes through
src/evaluation/truth.py:load_truth(split), so the dev half can be used without touching held-out labels.
src/analysis/ must never import this package.
"""
