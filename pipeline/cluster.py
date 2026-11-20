"""
cluster.py — unsupervised learning: groups the 37 states into market types.

k-means on 4 standardised features (protein deficiency, cancer proxy,
meat cost, demand). Tries k = 2, 3, 4 and keeps the best silhouette score.
Each cluster is named from its centre, so names are explainable.

Used by clean.py. Does NOT change scores or rankings; it adds `market_type`.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

FEATURES = ["protein_deficiency", "crc_index", "meat_cost", "demand"]
SEED = 42


def _name(centre: pd.Series) -> str:
    """Name a cluster from its centre (values are 0-100 scores)."""
    if centre["protein_deficiency"] >= 55 and centre["meat_cost"] >= 50:
        return "High need, price-squeezed"
    if centre["crc_index"] >= 55:
        return "Processed-meat heavy, lower protein need"
    return "Moderate, mixed"


def assign_market_types(states: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    states: one row per state with the FEATURES columns (0-100).
    Returns (states with 'cluster' and 'market_type', report dict).
    """
    X = states[FEATURES].astype(float).copy()
    X = X.fillna(X.median())                    # only for clustering
    Xs = StandardScaler().fit_transform(X)

    best = None
    scores = {}
    for k in (2, 3, 4):
        model = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Xs)
        score = silhouette_score(Xs, model.labels_)
        scores[k] = round(float(score), 3)
        if best is None or score > best[1] + 0.02:   # prefer fewer clusters on near-ties
            best = (k, score, model)

    k, score, model = best
    out = states.copy()
    out["cluster"] = model.labels_

    centres = X.groupby(model.labels_).mean()
    names = {c: _name(centres.loc[c]) for c in centres.index}

    # two clusters with the same name -> add a short suffix so they stay distinct
    seen = {}
    for c in sorted(names, key=lambda c: -centres.loc[c, "protein_deficiency"]):
        n = names[c]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[c] = f"{n} ({seen[n]})"

    out["market_type"] = out["cluster"].map(names)

    report = {
        "k": k,
        "silhouette": round(float(score), 3),
        "silhouette_by_k": scores,
        "groups": {
            names[c]: sorted(out.loc[out["cluster"] == c, "state"].str.title())
            for c in centres.index
        },
        "centres": {names[c]: {f: round(float(centres.loc[c, f])) for f in FEATURES}
                    for c in centres.index},
    }
    return out, report