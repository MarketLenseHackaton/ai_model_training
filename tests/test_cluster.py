import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "pipeline"))
from cluster import assign_market_types  # noqa: E402


def _two_groups():
    rows = []
    for i in range(6):   # northern-style: high need, expensive meat, few outlets
        rows.append({"state": f"N{i}", "protein_deficiency": 80 + i, "crc_index": 10 + i,
                     "meat_cost": 75 + i, "demand": 60})
    for i in range(6):   # southern-style: low need, many outlets
        rows.append({"state": f"S{i}", "protein_deficiency": 15 + i, "crc_index": 80 + i,
                     "meat_cost": 20 + i, "demand": 50})
    return pd.DataFrame(rows)


def test_finds_the_two_obvious_groups():
    out, report = assign_market_types(_two_groups())
    assert report["k"] == 2
    north = set(out[out["state"].str.startswith("N")]["market_type"])
    south = set(out[out["state"].str.startswith("S")]["market_type"])
    assert north == {"High need, price-squeezed"}
    assert south == {"Processed-meat heavy, lower protein need"}


def test_same_seed_same_groups():
    a, _ = assign_market_types(_two_groups())
    b, _ = assign_market_types(_two_groups())
    assert list(a["cluster"]) == list(b["cluster"])


def test_missing_values_do_not_crash():
    df = _two_groups()
    df.loc[0, "demand"] = None
    out, _ = assign_market_types(df)
    assert out["market_type"].notna().all()