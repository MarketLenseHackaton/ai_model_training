"""
cluster.py — unsupervised learning: groups the 37 states into market types.

k-means on standardised features (protein deficiency, cancer proxy,
meat cost, demand). Tries k = 2, 3, 4 and keeps the best silhouette score.
Each cluster is named from its centre, so names are explainable.

Safe with missing data:
- a feature with NO data at all (e.g. OSM file missing -> crc_index empty)
  is left out of the clustering, and the report says so
- a feature with a few gaps gets the median, only for clustering
- a feature where every state has the same value is left out (it can't split anything)

Used by clean.py. Does NOT change scores or rankings; it adds `market_type`.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

FEATURES = ["protein_deficiency", "crc_index", "meat_cost", "demand"]
SEED = 42
NOT_ENOUGH_DATA = "Not enough data to group"


def _name(centre: pd.Series) -> str:
    """Name a cluster from its centre (values are 0-100 scores). Missing counts as 0."""
    protein = centre.get("protein_deficiency", 0)
    meat = centre.get("meat_cost", 0)
    crc = centre.get("crc_index", 0)
    protein = 0 if pd.isna(protein) else protein
    meat = 0 if pd.isna(meat) else meat
    crc = 0 if pd.isna(crc) else crc

    if protein >= 55 and meat >= 50:
        return "High need, price-squeezed"
    if crc >= 55:
        return "Processed-meat heavy, lower protein need"
    return "Moderate, mixed"


def assign_market_types(states: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    states: one row per state with the FEATURES columns (0-100).
    Returns (states with 'cluster' and 'market_type', report dict).
    """
    X = states.reindex(columns=FEATURES).astype(float)

    # 1. drop features with no data at all
    skipped = [f for f in FEATURES if X[f].isna().all()]
    used = [f for f in FEATURES if f not in skipped]
    X = X[used].fillna(X[used].median())

    # 2. drop features where every state is the same (nothing to learn from)
    flat = [f for f in used if X[f].std() == 0]
    skipped += flat
    used = [f for f in used if f not in flat]

    out = states.copy()

    # 3. not enough to cluster -> everyone in one honest group
    if len(used) == 0 or len(X) < 4:
        out["cluster"] = 0
        out["market_type"] = NOT_ENOUGH_DATA
        report = {"k": 1, "silhouette": None, "silhouette_by_k": {},
                  "features_used": used, "features_skipped": skipped,
                  "groups": {NOT_ENOUGH_DATA: sorted(out["state"].astype(str).str.title())},
                  "centres": {}}
        return out, report

    Xs = StandardScaler().fit_transform(X[used])

    best = None
    scores = {}
    for k in (2, 3, 4):
        if k >= len(X):
            break
        model = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Xs)
        score = silhouette_score(Xs, model.labels_)
        scores[k] = round(float(score), 3)
        if best is None or score > best[1] + 0.02:   # prefer fewer clusters on near-ties
            best = (k, score, model)

    k, score, model = best
    out["cluster"] = model.labels_

    centres = X[used].groupby(model.labels_).mean()
    names = {c: _name(centres.loc[c]) for c in centres.index}

    # two clusters with the same name -> add a short suffix so they stay distinct
    order_col = "protein_deficiency" if "protein_deficiency" in used else used[0]
    seen = {}
    for c in sorted(names, key=lambda c: -centres.loc[c, order_col]):
        n = names[c]
        seen[n] = seen.get(n, 0) + 1
        if seen[n] > 1:
            names[c] = f"{n} ({seen[n]})"

    out["market_type"] = out["cluster"].map(names)

    report = {
        "k": k,
        "silhouette": round(float(score), 3),
        "silhouette_by_k": scores,
        "features_used": used,
        "features_skipped": skipped,
        "groups": {
            names[c]: sorted(out.loc[out["cluster"] == c, "state"].astype(str).str.title())
            for c in centres.index
        },
        "centres": {names[c]: {f: round(float(centres.loc[c, f])) for f in used}
                    for c in centres.index},
    }
    return out, report