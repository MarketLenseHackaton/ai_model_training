"""
plan.py — regulator and Discover helpers.

equity_overview(places) -> {"score", "by_area": [...]}
    Compares where businesses are with where the health need is.

discover_plan(place, lens) -> awareness plan for one place.
"""

from .scoring import health_score, _num

AREAS = ("big_city", "city", "rural")

MESSAGES = {
    "protein": "Good protein for every pot.",
    "cancer": "Add variety to your plate.",
}

ACTIVITIES = {
    "community_demo": {
        "title": "Community cooking demo",
        "description": "Cook a familiar dish with the product alongside a local women's group or community leader; give free tastes.",
        "effort": "low",
    },
    "market_tasting": {
        "title": "Market tasting stand",
        "description": "Cook stew with the product at a stall on market day; give free tastes and recipe cards.",
        "effort": "low",
    },
    "recipe_cards": {
        "title": "Picture recipe cards",
        "description": "Simple picture recipes in the local language, handed out with every pack.",
        "effort": "low",
    },
    "store_sampling": {
        "title": "In-store sampling",
        "description": "A weekend tasting table next to the meat section of one supermarket.",
        "effort": "medium",
    },
    "vendor_partner": {
        "title": "Partner with food vendors",
        "description": "Supply 2 buka or canteen owners for a week; they serve the product in one dish.",
        "effort": "low",
    },
    "campus_day": {
        "title": "Campus food day",
        "description": "Free tastes at a student or faculty event, with a short feedback form.",
        "effort": "low",
    },
}

ACTIVITIES_BY_CHANNEL = {
    "village_shop": ["community_demo", "market_tasting", "recipe_cards"],
    "open_market": ["market_tasting", "community_demo", "recipe_cards"],
    "supermarket": ["store_sampling", "recipe_cards", "vendor_partner"],
    "canteen": ["vendor_partner", "campus_day", "recipe_cards"],
    "restaurant": ["vendor_partner", "store_sampling", "recipe_cards"],
}
DEFAULT_ACTIVITIES = ["market_tasting", "vendor_partner", "recipe_cards"]

COUNT_BY_GAP = {"high": 3, "medium": 2, "low": 1}


def equity_overview(places: list[dict]) -> dict:
    """Where businesses are vs where the health need is, by area type."""
    businesses = {a: 0.0 for a in AREAS}
    need = {a: 0.0 for a in AREAS}

    for p in places:
        area = p.get("area_type")
        if area not in AREAS:
            continue
        businesses[area] += _num(p.get("registered")) or 0.0
        population = _num(p.get("population")) or 0.0
        need[area] += population * health_score(p, "both") / 100

    total_b = sum(businesses.values())
    total_n = sum(need.values())

    by_area = []
    gap = 0.0
    for a in AREAS:
        b_pct = 100 * businesses[a] / total_b if total_b else 0.0
        n_pct = 100 * need[a] / total_n if total_n else 0.0
        gap += abs(b_pct - n_pct)
        by_area.append({
            "area": a,
            "business_pct": int(round(b_pct)),
            "need_pct": int(round(n_pct)),
        })

    return {"score": int(round(max(0.0, 100.0 - gap))), "by_area": by_area}


def _message(place: dict, lens: str) -> str:
    if lens == "cancer":
        return MESSAGES["cancer"]
    if lens == "protein":
        return MESSAGES["protein"]
    protein = _num(place.get("protein_deficiency"))
    cancer = _num(place.get("crc_index"))
    if cancer is not None and (protein is None or cancer > protein):
        return MESSAGES["cancer"]
    return MESSAGES["protein"]


def discover_plan(place: dict, lens: str) -> dict:
    """Awareness plan for one place. Backend adds recipes + feedback summary."""
    gap = place.get("awareness_gap", "medium")
    if gap not in COUNT_BY_GAP:
        gap = "medium"

    keys = ACTIVITIES_BY_CHANNEL.get(place.get("channel"), DEFAULT_ACTIVITIES)
    chosen = [dict(ACTIVITIES[k]) for k in keys[:COUNT_BY_GAP[gap]]]

    return {
        "place_id": place.get("id"),
        "awareness_gap": gap,
        "lens": lens,
        "message": _message(place, lens),
        "activities": chosen,
    }