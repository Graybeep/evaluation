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
    n_distinct: int = -1        # distinct input values; 1 => degenerate by construction

    @property
    def width(self) -> float:
        return self.high - self.low

    @property
    def degenerate(self) -> bool:
        """Zero width because every resampled value is identical — not because the
        estimate is precise.

        A percentile bootstrap over N identical values returns a zero-width interval. That
        is the correct output, and it is NOT evidence of confidence: it says the statistic
        has no variance across scenarios, which for a composite means every scenario landed
        in the same severity band. Reporting `[65.0, 65.0]` without this flag invites
        exactly the wrong reading.
        """
        return self.n_distinct == 1 and self.n > 1

    def as_dict(self) -> dict:
        return {"point": round(self.point, 4), "low": round(self.low, 4),
                "high": round(self.high, 4), "method": self.method, "n": self.n,
                "n_distinct": self.n_distinct, "degenerate": self.degenerate}


def bootstrap_ci(values: list[float], stat=None, draws: int = BOOTSTRAP_DRAWS,
                 alpha: float = DEFAULT_ALPHA, seed: int = 12345) -> Interval:
    """Percentile bootstrap over *scenario-level* values (resample scenarios, not runs)."""
    stat = stat or (lambda xs: sum(xs) / len(xs))
    n = len(values)
    if n == 0:
        return Interval(float("nan"), float("nan"), float("nan"), "bootstrap", 0, 0)
    if n == 1:
        p = stat(values)
        return Interval(p, p, p, "bootstrap(n=1)", 1, n_distinct=1)
    rng = random.Random(seed)
    point = stat(values)
    draws_out = []
    for _ in range(draws):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        draws_out.append(stat(sample))
    draws_out.sort()
    lo = draws_out[max(0, int((alpha / 2) * draws) - 1)]
    hi = draws_out[min(draws - 1, int((1 - alpha / 2) * draws))]
    return Interval(point, lo, hi, "bootstrap", n, n_distinct=len(set(values)))


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


# ------------------------------------------------------ agreement (§6.3, §11.1)
@dataclass
class Kappa:
    kappa: float
    observed_agreement: float
    expected_agreement: float
    n: int
    low: float = float("nan")
    high: float = float("nan")

    @property
    def interpretation(self) -> str:
        k = self.kappa
        if k < 0.0:   return "worse than chance"
        if k < 0.20:  return "slight"
        if k < 0.40:  return "fair"
        if k < 0.60:  return "moderate — BELOW the §6.3 shipping threshold"
        if k < 0.80:  return "substantial"
        return "almost perfect"

    def as_dict(self) -> dict:
        return {"kappa": round(self.kappa, 4), "n": self.n,
                "observed_agreement": round(self.observed_agreement, 4),
                "expected_agreement": round(self.expected_agreement, 4),
                "ci_low": round(self.low, 4), "ci_high": round(self.high, 4),
                "interpretation": self.interpretation}


class KappaRequiresHumanLabels(RuntimeError):
    """`cohens_kappa` was called without human labels. See §11.1."""


def cohens_kappa(a: list, b: list, bootstrap: int = 2000, seed: int = 7,
                 *, human_labels: bool = False) -> Kappa:
    """Cohen's kappa with a percentile bootstrap CI. **Gated — see below.**

    Chance-corrected on purpose: raw agreement flatters any rater pair on a skewed label
    distribution, and judge-eligible traces are heavily skewed toward "no finding".

    ## Why this raises by default (§7.10)

    This function was implemented and then called from nowhere. That is a worse state than
    not having it: a reader skimming `score/stats.py` sees a kappa implementation next to
    the bootstrap and the McNemar test and reasonably concludes agreement **was measured**.
    Same family as `judge_version()` returning `"unavailable"` while the judge was
    answering — the artifact says one thing and the system does another.

    Deleting it is the wrong fix, because the maths is correct and §11.1 names the κ study
    as the one genuinely closable gap. So it is **gated instead of removed**: reachable,
    reviewable, and impossible to reach by accident.

    The gate is not about the arithmetic — κ computes fine on any two label lists. It is
    about **what the number would mean**. Against judge-vs-judge labels it measures the
    judge's *self-consistency*, which is not calibration and would be read as calibration.
    Only human labels make it the statistic §6.3 needs, and none have been produced.

    Pass `human_labels=True` only when `a` and `b` are genuinely independent human labels
    (or one human set and one judge set). That flag is a claim about provenance, and it is
    the caller's to make honestly — nothing here can check it.
    """
    if not human_labels:
        raise KappaRequiresHumanLabels(
            "cohens_kappa() requires human labels and none exist in this repo (§11.1). "
            "No agreement study has been run, so any kappa computed here would measure "
            "judge-vs-judge self-consistency and be read as calibration. If you have "
            "produced real human labels, pass human_labels=True and record how they were "
            "collected. Do not pass it to silence this error.")
    if len(a) != len(b):
        raise ValueError("label lists must be the same length")
    n = len(a)
    if n == 0:
        return Kappa(float("nan"), float("nan"), float("nan"), 0)

    def _k(xs, ys):
        m = len(xs)
        obs = sum(1 for x, y in zip(xs, ys) if x == y) / m
        cats = set(xs) | set(ys)
        exp = sum((xs.count(c) / m) * (ys.count(c) / m) for c in cats)
        return (obs - exp) / (1 - exp) if exp != 1 else 1.0, obs, exp

    k, obs, exp = _k(list(a), list(b))
    rng = random.Random(seed)
    draws = []
    for _ in range(bootstrap):
        idx = [rng.randrange(n) for _ in range(n)]
        try:
            draws.append(_k([a[i] for i in idx], [b[i] for i in idx])[0])
        except ZeroDivisionError:
            continue
    draws.sort()
    lo = draws[int(0.025 * len(draws))] if draws else float("nan")
    hi = draws[min(len(draws) - 1, int(0.975 * len(draws)))] if draws else float("nan")
    return Kappa(k, obs, exp, n, lo, hi)
