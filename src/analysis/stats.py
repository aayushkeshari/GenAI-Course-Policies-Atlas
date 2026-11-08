"""Shared inference helpers for P2: cluster bootstrap (ANL-05, ANL-14) and chi-square / Cramér's V (ANL-06, ANL-12).

Cluster bootstrap: institutions (inst_id) are resampled with replacement, keeping all of an institution's
rows together, because rows within an institution are not independent (ANL-14). It is vectorized: per-
institution sums are computed once, and each resample is a weight vector (how many times each institution
was drawn), so a bootstrap statistic is (weights @ per-institution numerators) / (weights @ denominators).
CIs are percentile intervals.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

N_BOOT = 2000
SEED = 4005
CI = 0.95
BOOTSTRAP_INFO = {"method": "cluster bootstrap (percentile)", "cluster": "inst_id", "resamples": N_BOOT,
                  "seed": SEED, "ci_level": CI}


class ClusterBootstrap:
    """Resample weights for the institutions present in `cluster_ids` (one entry per row)."""

    def __init__(self, cluster_ids: pd.Series, n_boot: int = N_BOOT, seed: int = SEED):
        self.codes, self.clusters = pd.factorize(cluster_ids, sort=True)
        k = len(self.clusters)
        rng = np.random.default_rng(seed)
        self.weights = rng.multinomial(k, np.full(k, 1.0 / k), size=n_boot).astype(float)  # (B, K)

    def sums(self, values: np.ndarray) -> np.ndarray:
        """Per-institution sums of a row-level array."""
        return np.bincount(self.codes, weights=np.asarray(values, dtype=float), minlength=len(self.clusters))

    def ratio(self, num: np.ndarray, den: np.ndarray) -> np.ndarray:
        """Bootstrap distribution of sum(num)/sum(den) (row-level arrays)."""
        n, d = self.weights @ self.sums(num), self.weights @ self.sums(den)
        with np.errstate(invalid="ignore", divide="ignore"):
            return n / d


def interval(boot: np.ndarray) -> tuple[float, float]:
    a = (1 - CI) / 2 * 100
    lo, hi = np.nanpercentile(boot, [a, 100 - a])
    return float(lo), float(hi)


def _record(by, group, outcome, category, est, boot, n_rows, n_clusters):
    lo, hi = interval(boot)
    return {"by": by, "group": str(group), "outcome": outcome, "category": str(category), "estimate": float(est),
            "ci_low": lo, "ci_high": hi, "n_rows": int(n_rows), "n_clusters": int(n_clusters)}


def _groups(df: pd.DataFrame, by: str, order: list | None) -> list:
    present = set(df[by].dropna().unique())
    return [g for g in order if g in present] if order else sorted(present, key=str)


def share_records(df: pd.DataFrame, by: str, outcome: str, categories: list, cb: ClusterBootstrap,
                  outcome_name: str | None = None, order: list | None = None) -> list[dict]:
    """Share of each outcome category within each group of `by`, with cluster-bootstrap CIs.
    `df` must be the same rows (same order) that built `cb`."""
    out = []
    for g in _groups(df, by, order):
        den = (df[by] == g).to_numpy()
        inst = df.loc[den, "inst_id"].nunique()
        for c in categories:
            num = den & (df[outcome] == c).to_numpy()
            est = num.sum() / den.sum()
            out.append(_record(by, g, outcome_name or outcome, c, est, cb.ratio(num, den), den.sum(), inst))
    return out


def mean_records(df: pd.DataFrame, by: str, value: str, cb: ClusterBootstrap, order: list | None = None) -> list[dict]:
    """Mean of a numeric column within each group of `by`, with cluster-bootstrap CIs."""
    out = []
    vals = df[value].astype(float).to_numpy()
    for g in _groups(df, by, order):
        den = (df[by] == g).to_numpy()
        num = np.where(den, vals, 0.0)
        est = num.sum() / den.sum()
        out.append(_record(by, g, value, "mean", est, cb.ratio(num, den), den.sum(), df.loc[den, "inst_id"].nunique()))
    return out


def contingency(df: pd.DataFrame, row: str, col: str) -> tuple[list, list, np.ndarray]:
    rows = sorted(df[row].unique(), key=str)
    cols = sorted(df[col].unique(), key=str)
    table = np.array([[((df[row] == r) & (df[col] == c)).sum() for c in cols] for r in rows], dtype=float)
    return rows, cols, table


def cramers_v(table: np.ndarray) -> np.ndarray:
    """Cramér's V for one table (r, c) or a stack of tables (B, r, c)."""
    t = np.asarray(table, dtype=float)
    n = t.sum(axis=(-2, -1), keepdims=True)
    expected = t.sum(axis=-1, keepdims=True) * t.sum(axis=-2, keepdims=True) / n
    with np.errstate(invalid="ignore", divide="ignore"):
        chi2 = np.nansum(np.where(expected > 0, (t - expected) ** 2 / expected, 0.0), axis=(-2, -1))
    k = min(t.shape[-2], t.shape[-1]) - 1
    return np.sqrt(chi2 / (n.squeeze((-2, -1)) * k))


def association(df: pd.DataFrame, row: str, col: str, cb: ClusterBootstrap) -> dict:
    """Chi-square test (naive: rows treated as independent) and Cramér's V with a cluster-bootstrap CI,
    which is the main inference (ANL-14)."""
    rows, cols, table = contingency(df, row, col)
    chi2, p, dof, _ = chi2_contingency(table, correction=False)
    cell = np.zeros(len(df), dtype=int)
    for i, r in enumerate(rows):
        for j, c in enumerate(cols):
            cell[((df[row] == r) & (df[col] == c)).to_numpy()] = i * len(cols) + j
    per_cluster = np.zeros((len(cb.clusters), table.size))
    np.add.at(per_cluster, (cb.codes, cell), 1.0)
    boot_tables = (cb.weights @ per_cluster).reshape(-1, len(rows), len(cols))
    lo, hi = interval(cramers_v(boot_tables))
    return {"row": row, "col": col, "row_levels": [str(r) for r in rows], "col_levels": [str(c) for c in cols],
            "table": table.astype(int).tolist(), "n": int(table.sum()), "n_clusters": int(df["inst_id"].nunique()),
            "chi2": float(chi2), "dof": int(dof),
            "p_value_naive": float(p),
            "p_value_note": "naive: treats course-term rows as independent; not the main inference (ANL-14)",
            "cramers_v": float(cramers_v(table)),
            "cramers_v_ci": [lo, hi],
            "cramers_v_ci_method": "cluster bootstrap over inst_id (main inference)"}
