"""
ranking.py — turns all places into the ranked result the API returns.

rank(places, weights, lens, fair_share) -> {"ranked", "full", "equity", "meta"}

Steps:
1. score every place          (scoring.total_score)
2. split off full places      (scoring.status == "full")
3. sort open places           (highest total first; ties -> rural first)
4. fair-share (optional)      (at least 2 rural places in the top 5)
5. equity check               (how many rural places are in the top 5)
"""

from .scoring import health_score, total_score, status

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
        "uncertain": "Confidence not calculated yet.",
        "test_first": "Run a small trial before stocking.",
    }


def _build_item(place: dict, total: int, lens: str) -> dict:
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
            "low": total,    # Step 4 (simulation) will replace this
            "high": total,   # Step 4 (simulation) will replace this
        },
        "confidence": {"pct": 50, "label": "medium"},  # Step 4 replaces this
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
        # best rural place below the top 5
        candidate = next((it for it in rest if it["is_rural"]), None)
        if candidate is None:
            break
        # lowest non-rural place inside the top 5
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
    open_items = []
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
            continue
        total = total_score(place, weights, lens)
        open_items.append(_build_item(place, total, lens))

    # highest total first; on a tie, rural first; then by name for stability
    open_items.sort(key=lambda it: (-it["scores"]["total"],
                                    not it["is_rural"],
                                    it["name"]))

    if fair_share:
        open_items = _apply_fair_share(open_items)

    for position, item in enumerate(open_items, start=1):
        item["rank"] = position

    return {
        "ranked": open_items,
        "full": full,
        "equity": _equity(open_items),
        "meta": {
            "n_simulations": n_sims,
            "seed": seed,
            "data_as_of": None,   # backend can fill this from its data
            "lens": lens,
        },
    }