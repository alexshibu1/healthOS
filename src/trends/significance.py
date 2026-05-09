"""
Statistical helpers for month-over-month trends.

Spec: src/trends/spec.md — Cohen's d + Mann-Whitney / Welch t-test;
significant iff |d| > 0.3 and p < 0.05.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
from scipy import stats

TestKind = Literal["mannwhitney", "welch_t"]


def cohens_d_independent(a: np.ndarray, b: np.ndarray) -> float:
    """
    Cohen's d using pooled standard deviation (two independent samples).

    Returns 0.0 if denominator is zero or sample sizes insufficient.
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if a.size < 2 or b.size < 2:
        return float("nan")
    m1, m2 = float(np.mean(a)), float(np.mean(b))
    v1, v2 = float(np.var(a, ddof=1)), float(np.var(b, ddof=1))
    n1, n2 = a.size, b.size
    pooled_var = ((n1 - 1) * v1 + (n2 - 1) * v2) / max(n1 + n2 - 2, 1)
    if pooled_var <= 0 or not np.isfinite(pooled_var):
        return 0.0
    sp = np.sqrt(pooled_var)
    return (m1 - m2) / sp


def p_value_two_sample(
    curr: np.ndarray,
    prev: np.ndarray,
    kind: TestKind,
) -> float:
    """Two-sided p-value for independent samples."""
    c = np.asarray(curr, dtype=float)
    p = np.asarray(prev, dtype=float)
    c = c[np.isfinite(c)]
    p = p[np.isfinite(p)]
    if c.size < 2 or p.size < 2:
        return float("nan")
    if kind == "mannwhitney":
        _, pv = stats.mannwhitneyu(c, p, alternative="two-sided")
        return float(pv)
    # Welch's t-test
    _, pv = stats.ttest_ind(c, p, equal_var=False, alternative="two-sided")
    return float(pv)


def is_significant(d: float, p: float) -> bool:
    """Both |d| > 0.3 and p < 0.05."""
    if not (np.isfinite(d) and np.isfinite(p)):
        return False
    return abs(d) > 0.3 and p < 0.05
