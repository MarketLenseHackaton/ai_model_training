"""
simulate.py — Monte Carlo confidence.

Runs the ranking n_sims times with every input nudged by an amount that
depends on its data label, and the weights nudged by +/-20%.

For each place returns:
  pct   = % of runs where the place is in the top 5
  label = "high" (>=70) / "medium" (40-69) / "low" (<40)
  low   = 10th percentile of its total score
  high  = 90th percentile of its total score
"""

import numpy as np

TOP_N = 5
WEIGHT_SPREAD = 0.20
LABEL_SPREAD = {"measured": 0.10, "estimated": 0.25, "assumed": 0.40}
DEFAULT_SPREAD = LABEL_SPREAD["assumed"]   # unknown label = least trusted


def _spread(label) -> float:
    return LABEL_SPREAD.get(label, DEFAULT_SPREAD)


def _array(places, key) -> np.ndarray:
    """Values for one field as floats; missing values become NaN."""
    out = []
    for p in places:
        v = p.get(key)
        try:
            out.append(float(v) if v not in (None, "") else np.nan)
        except (TypeError, ValueError):
            out.append(np.nan)
    return np.array(out, dtype=float)


def _noisy(values, spreads, rng, n_sims) -> np.ndarray:
    """(n_sims x n_places) copies of values, each multiplied by random noise."""
    low = 1.0 - spreads
    high = 1.0 + spreads
    noise = rng.uniform(low, high, size=(n_sims, len(values)))
    return np.clip(values * noise, 0, 100)   # NaN stays NaN


def confidence_label(pct: int) -> str:
    if pct >= 70:
        return "high"
    if pct >= 40:
        return "medium"
    return "low"


def simulate(places: list[dict], weights: dict, lens: str,
             n_sims: int = 1000, seed: int = 42) -> dict:
    """Returns {place_id: {"pct", "label", "low", "high"}} for OPEN places."""
    n = len(places)
    if n == 0:
        return {}

    rng = np.random.default_rng(seed)

    # --- inputs and how much we trust each one ---
    demand = _array(places, "demand")
    protein = _array(places, "protein_deficiency")
    cancer = _array(places, "crc_index")
    meat = _array(places, "meat_cost")

    s_demand = np.array([_spread(p.get("label_demand")) for p in places])
    s_health = np.array([_spread(p.get("label_health")) for p in places])
    s_meat = np.array([_spread(p.get("label_meat_cost")) for p in places])

    # --- 1,000 noisy versions of every input ---
    D = np.nan_to_num(_noisy(demand, s_demand, rng, n_sims))
    P = _noisy(protein, s_health, rng, n_sims)
    C = _noisy(cancer, s_health, rng, n_sims)
    M = np.nan_to_num(_noisy(meat, s_meat, rng, n_sims))

    # --- health by lens (missing data = 0, never guessed) ---
    if lens == "protein":
        H = np.nan_to_num(P)
    elif lens == "cancer":
        H = np.nan_to_num(C)
    else:  # both: average of whatever exists
        stacked = np.stack([P, C])
        count = np.sum(~np.isnan(stacked), axis=0)
        total_h = np.nansum(stacked, axis=0)
        H = np.where(count > 0, total_h / np.maximum(count, 1), 0.0)

    # --- noisy weights, one set per run ---
    base = np.array([weights["demand"], weights["health"],
                     weights["affordability"]], dtype=float)
    W = base * rng.uniform(1 - WEIGHT_SPREAD, 1 + WEIGHT_SPREAD, size=(n_sims, 3))
    wd, wh, wa = W[:, [0]], W[:, [1]], W[:, [2]]

    totals = (wd * D + wh * H + wa * M) / (wd + wh + wa)   # (n_sims x n)

    # --- position of every place in every run (0 = best) ---
    order = np.argsort(-totals, axis=1)
    positions = np.empty_like(order)
    rows = np.arange(n_sims)[:, None]
    positions[rows, order] = np.arange(n)

    in_top = (positions < TOP_N).sum(axis=0)
    low = np.percentile(totals, 10, axis=0)
    high = np.percentile(totals, 90, axis=0)

    result = {}
    for i, p in enumerate(places):
        pct = int(round(100 * in_top[i] / n_sims))
        result[p["id"]] = {
            "pct": pct,
            "label": confidence_label(pct),
            "low": int(round(low[i])),
            "high": int(round(high[i])),
        }
    return result