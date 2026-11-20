"""
explain.py — plain-language reasons for every ranked place.

Template-based on purpose: the text only uses the place's own data,
never invents numbers, and never makes health or cure claims.
"""

LABEL_WORDS = {
    "measured": "measured from official data",
    "estimated": "estimated from surveys and interviews",
    "assumed": "a team assumption",
}

TESTS_BY_CHANNEL = {
    "open_market": "Sell 50 trial packs at 2 market stalls for 2 weeks; count repeat buyers.",
    "supermarket": "Weekend sampling in 1 supermarket; track packs sold over 2 weeks.",
    "canteen": "Put one soy-chunk dish on the menu for 5 days; compare plates sold with the meat version.",
    "restaurant": "Add one menu item with 1 restaurant partner for 2 weeks.",
    "village_shop": "Field visit plus a 20-person tasting before stocking any shop.",
}
DEFAULT_TEST = "Run a small 2-week trial with one local seller."
LOW_CONFIDENCE_TEST = "Run a 20-person tasting and short survey first, before spending on stock."


def _num(value):
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:          # NaN from pandas = missing
        return None
    return f


def _level(value: float) -> str:
    if value >= 70:
        return "high"
    if value >= 40:
        return "moderate"
    return "low"


def demand_text(place: dict) -> str:
    demand = _num(place.get("demand")) or 0.0
    if demand >= 70:
        start = "Strong interest here"
    elif demand >= 40:
        start = "Some interest here"
    else:
        start = "Weak demand signal so far"
    label = LABEL_WORDS.get(place.get("label_demand"), LABEL_WORDS["assumed"])
    return f"{start} ({label})."


def _protein_sentence(place: dict) -> str:
    protein = _num(place.get("protein_deficiency"))
    if protein is None:
        return "No protein deficiency data for this place."
    return f"{_level(protein).capitalize()} protein deficiency reported."


def _cancer_sentence(place: dict) -> str:
    cancer = _num(place.get("crc_index"))
    if cancer is None:
        return "No colorectal cancer data for this place."
    return (f"{_level(cancer).capitalize()} colorectal cancer and "
            f"processed-meat intake signal.")


def health_text(place: dict, lens: str) -> str:
    if lens == "protein":
        return _protein_sentence(place)
    if lens == "cancer":
        return _cancer_sentence(place)
    return f"{_protein_sentence(place)} {_cancer_sentence(place)}"


def affordability_text(place: dict) -> str:
    meat = _num(place.get("meat_cost")) or 0.0
    if meat >= 70:
        return "Meat is far more expensive than average here."
    if meat >= 40:
        return "Meat is somewhat expensive here."
    return "Meat is affordable here, so price is not the main reason to switch."


def uncertain_text(place: dict, lens: str, confidence_pct: int) -> str:
    parts = [f"Stays in the top 5 in {confidence_pct}% of 1,000 simulated runs."]

    weak = []
    if place.get("label_demand") == "assumed":
        weak.append("demand")
    if place.get("label_health") == "assumed":
        weak.append("health data")
    if place.get("label_meat_cost") == "assumed":
        weak.append("meat prices")
    if weak:
        parts.append("Team assumptions: " + ", ".join(weak) + ".")

    if lens in ("cancer", "both") and _num(place.get("crc_index")) is None:
        parts.append("No cancer data, so it counts as zero.")

    if len(parts) == 1:
        parts.append("All inputs are measured or estimated.")
    return " ".join(parts)


def test_first_text(place: dict, confidence_label: str) -> str:
    if confidence_label == "low":
        return LOW_CONFIDENCE_TEST
    return TESTS_BY_CHANNEL.get(place.get("channel"), DEFAULT_TEST)


def explain(place: dict, lens: str, confidence: dict) -> dict:
    """The 'explanation' object of one ranked item (contract shape)."""
    return {
        "demand": demand_text(place),
        "health": health_text(place, lens),
        "affordability": affordability_text(place),
        "uncertain": uncertain_text(place, lens, confidence["pct"]),
        "test_first": test_first_text(place, confidence["label"]),
    }