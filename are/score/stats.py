"""Statistics (CLAUDE.md §8.2). Pure functions, no dependencies beyond the stdlib.

The one idea this file exists to enforce: **the scenario is the unit of analysis, not the
run.** With N correlated runs per scenario, treating M·N as independent understates
standard errors by roughly sqrt(N) and produces confidence intervals that are a lie.
Every function here resamples or tests over *scenarios*.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

BOOTSTRAP_DRAWS = 2000
DEFAULT_ALPHA = 0.05


@dataclass
class Interval:
    point: float
    low: float
    high: float
    method: str
    n: int

    @property
    def width(self) -> float:
        return self.high - self.low

    def as_dict(self) -> dict:
        return {"point": round(self.point, 4), "low": round(self.low, 4),
                "high": round(self.high, 4), "method": self.method, "n": self.n}


def bootstrap_ci(values: list[float], stat=None, draws: int = BOOTSTRAP_DRAWS,
                 alpha: float = DEFAULT_ALPHA, seed: int = 12345) -> Interval:
    """Percentile bootstrap over *scenario-level* values (resample scenarios, not runs)."""
    stat = stat or (lambda xs: sum(xs) / len(xs))
    n = len(values)
    if n == 0:
        return Interval(float("nan"), float("nan"), float("nan"), "bootstrap", 0)
    if n == 1:
        p = stat(values)
        return Interval(p, p, p, "bootstrap(n=1)", 1)
    rng = random.Random(seed)
    point = stat(values)
    draws_out = []
    for _ in range(draws):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        draws_out.append(stat(sample))
    draws_out.sort()
    lo = draws_out[max(0, int((alpha / 2) * draws) - 1)]
    hi = draws_out[min(draws - 1, int((1 - alpha / 2) * draws))]
    return Interval(point, lo, hi, "bootstrap", n)


def wilson_ci(successes: float, n: int, alpha: float = DEFAULT_ALPHA) -> Interval:
    """Fallback interval for a proportion (§12: 'bootstrap buggy at 2am')."""
    if n == 0:
        return Interval(float("nan"), float("nan"), float("nan"), "wilson", 0)
    z = 1.959963984540054 if abs(alpha - 0.05) < 1e-9 else _z_for(alpha)
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return Interval(p, max(0.0, centre - half), min(1.0, centre + half), "wilson", n)


def _z_for(alpha: float) -> float:
    # Acklam-style inverse normal, adequate for reporting intervals
    p = 1 - alpha / 2
    a = [-39.69683028665376, 220.9460984245205, -275.9285104469687,
         138.3577518672690, -30.66479806614716, 2.506628277459239]
    b = [-54.47609879822406, 161.5858368580409, -155.6989798598866,
         66.80131188771972, -13.28068155288572]
    c = [-0.007784894002430293, -0.3223964580411365, -2.400758277161838,
         -2.549732539343734, 4.374664141464968, 2.938163982698783]
    d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# --------------------------------------------------------------- paired tests
@dataclass
class McNemar:
    b: int          # A pass -> B fail
    c: int          # A fail -> B pass
    p_value: float
    n_discordant: int
    method: str = "exact binomial"

    def as_dict(self) -> dict:
        return {"a_pass_b_fail": self.b, "a_fail_b_pass": self.c,
                "n_discordant": self.n_discordant, "p_value": round(self.p_value, 5),
                "method": self.method}


def _binom_cdf(k: int, n: int, p: float = 0.5) -> float:
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(0, k + 1))


def mcnemar(b: int, c: int) -> McNemar:
    """Exact two-sided McNemar on discordant pairs. Version comparison must be paired."""
    n = b + c
    if n == 0:
        return McNemar(b, c, 1.0, 0, "exact binomial (no discordant pairs)")
    k = min(b, c)
    p = min(1.0, 2 * _binom_cdf(k, n, 0.5))
    return McNemar(b, c, p, n)


def benjamini_hochberg(pvalues: list[float], q: float = 0.10) -> list[bool]:
    """BH at q across the category tests (§8.2). Uncorrected, you cry wolf every release."""
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    reject = [False] * m
    kmax = -1
    for rank, i in enumerate(order, start=1):
        if pvalues[i] <= q * rank / m:
            kmax = rank
    for rank, i in enumerate(order, start=1):
        if rank <= kmax:
            reject[i] = True
    return reject
