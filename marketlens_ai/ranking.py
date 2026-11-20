"""
ranking.py — turns all places into the ranked result the API returns.

rank(places, weights, lens, fair_share) -> {"ranked", "full", "equity", "meta"}

Steps:
1. split off full places      (scoring.status == "full")
2. score every open place     (scoring.total_score)
3. confidence + score range   (simulate.simulate, 1,000 runs)
4. sort                       (highest total; ties -> higher confidence, then rural)
5. fair-share (optional)      (at least 2 rural places in the top 5)
6. equity check               (how many rural places are in the top 5)
"""

from .scoring import health_score, total_score, status
from .simulate import simulate

TOP_N = 5
RURAL_TARGET = 2


def _is_rural(place: dict) -> bool:
    return place.get("area_type") == "rural"


def _placeholder_explanation(place: dict) -> dict:
    # Replaced by explain.py in Step 5. Shape is final.
    return {
        "demand": "Explanation coming soon.",
        "health": "Explanation coming soon.",
        "affordability": "Explanation coming soon.",
        "uncertain": "See confidence and score range.",
        "test_first": "Run a small trial before stocking.",
    }


def _build_item(place: dict, total: int, lens: str, sim: dict) -> dict:
    """One entry of 'ranked', in the exact contract shape."""
    capacity = int(place.get("capacity") or 0)
    registered = int(place.get("registered") or 0)
    return {
        "rank": 0,  # filled in after sorting
        "id": place["id"],
        "name": place.get("name", ""),
        "area_type": place.get("area_type", ""),
        "is_rural": _is_rural(place),
        "segment": place.get("segment", ""),
        "channel": place.get("channel", ""),
        "scores": {
            "demand": int(round(float(place.get("demand") or 0))),
            "health": int(round(health_score(place, lens))),
            "affordability": int(round(float(place.get("meat_cost") or 0))),
            "total": total,
            "low": min(sim["low"], total),
            "high": max(sim["high"], total),
        },
        "confidence": {"pct": sim["pct"], "label": sim["label"]},
        "capacity": {
            "registered": registered,
            "capacity": capacity,
            "slots_left": max(0, capacity - registered),
            "status": status(place),
        },
        "explanation": _placeholder_explanation(place),
        "labels": {
            "demand": place.get("label_demand", "assumed"),
            "health": place.get("label_health", "assumed"),
            "affordability": place.get("label_meat_cost", "assumed"),
        },
        "fair_share_added": False,
    }


def _apply_fair_share(items: list[dict]) -> list[dict]:
    """Make sure at least RURAL_TARGET rural places are in the top TOP_N."""
    top = items[:TOP_N]
    rest = items[TOP_N:]

    rural_in_top = sum(1 for it in top if it["is_rural"])
    while rural_in_top < RURAL_TARGET:
        candidate = next((it for it in rest if it["is_rural"]), None)
        if candidate is None:
            break
        out_index = next(
            (i for i in range(len(top) - 1, -1, -1) if not top[i]["is_rural"]),
            None,
        )
        if out_index is None:
            break

        pushed_out = top.pop(out_index)
        rest.remove(candidate)
        candidate["fair_share_added"] = True
        top.append(candidate)
        rest.insert(0, pushed_out)
        rural_in_top += 1

    return top + rest


def _equity(items: list[dict]) -> dict:
    rural_in_top = sum(1 for it in items[:TOP_N] if it["is_rural"])
    return {
        "rural_in_top5": rural_in_top,
        "target": RURAL_TARGET,
        "balanced": rural_in_top >= RURAL_TARGET,
    }


def rank(places: list[dict], weights: dict, lens: str,
         fair_share: bool = False, n_sims: int = 1000, seed: int = 42) -> dict:
    open_places = []
    full = []

    for place in places:
        if status(place) == "full":
            full.append({
                "id": place["id"],
                "name": place.get("name", ""),
                "segment": place.get("segment", ""),
                "registered": int(place.get("registered") or 0),
                "capacity": int(place.get("capacity") or 0),
            })
        else:
            open_places.append(place)

    # validates weights + lens and gives the exact total for each place
    totals = {p["id"]: total_score(p, weights, lens) for p in open_places}

    sims = simulate(open_places, weights, lens, n_sims=n_sims, seed=seed)

    items = [_build_item(p, totals[p["id"]], lens, sims[p["id"]])
             for p in open_places]

    # highest total; tie -> higher confidence, then rural, then name
    items.sort(key=lambda it: (-it["scores"]["total"],
                               -it["confidence"]["pct"],
                               not it["is_rural"],
                               it["name"]))

    if fair_share:
        items = _apply_fair_share(items)

    for position, item in enumerate(items, start=1):
        item["rank"] = position

    return {
        "ranked": items,
        "full": full,
        "equity": _equity(items),
        "meta": {
            "n_simulations": n_sims,
            "seed": seed,
            "data_as_of": None,   # backend can fill this from its data
            "lens": lens,
        },
    }