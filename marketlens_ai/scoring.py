"""
scoring.py — the math for ONE place.

health_score     -> how big the health need is (depends on the lens)
total_score      -> weighted average of the 3 checks (0-100)
status           -> open / nearly_full / full
suggest_capacity -> how many businesses this place can hold
"""

VALID_LENSES = ("protein", "cancer", "both")
VALID_WEIGHTS = (1, 2, 3)          # Low, Medium, High
NEARLY_FULL_AT = 0.8               # 80% of slots used
PEOPLE_PER_SLOT = 1_500_000        # our stated assumption: 1 alt-protein business per 1.5M people at full need


def _num(value):
    """Turn a value into a float, or None if it is missing/empty."""
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f != f:          # NaN (pandas uses NaN for empty cells)
        return None
    return f


def health_score(place: dict, lens: str) -> float:
    """Health need for this place, 0-100, depending on the lens."""
    if lens not in VALID_LENSES:
        raise ValueError(f"lens must be one of {VALID_LENSES}, got {lens!r}")

    protein = _num(place.get("protein_deficiency"))
    cancer = _num(place.get("crc_index"))

    if lens == "protein":
        return protein if protein is not None else 0.0
    if lens == "cancer":
        return cancer if cancer is not None else 0.0

    # lens == "both": average only the values we actually have
    available = [v for v in (protein, cancer) if v is not None]
    if not available:
        return 0.0
    return sum(available) / len(available)


def total_score(place: dict, weights: dict, lens: str) -> int:
    """Weighted average of demand, health and meat cost. Returns 0-100."""
    w_d = weights.get("demand")
    w_h = weights.get("health")
    w_a = weights.get("affordability")
    for name, w in (("demand", w_d), ("health", w_h), ("affordability", w_a)):
        if w not in VALID_WEIGHTS:
            raise ValueError(f"weight '{name}' must be 1, 2 or 3, got {w!r}")

    demand = _num(place.get("demand")) or 0.0
    health = health_score(place, lens)
    meat_cost = _num(place.get("meat_cost")) or 0.0

    total = (w_d * demand + w_h * health + w_a * meat_cost) / (w_d + w_h + w_a)
    return int(round(total))


def status(place: dict) -> str:
    """'open', 'nearly_full' or 'full'."""
    capacity = int(_num(place.get("capacity")) or 0)
    registered = int(_num(place.get("registered")) or 0)

    if capacity <= 0 or registered >= capacity:
        return "full"
    if registered / capacity >= NEARLY_FULL_AT:
        return "nearly_full"
    return "open"


def suggest_capacity(place: dict) -> int:
    """Suggested number of business slots. Always at least 1."""
    population = _num(place.get("population")) or 0.0
    demand = _num(place.get("demand")) or 0.0
    health = health_score(place, "both")

    slots = population / PEOPLE_PER_SLOT * (demand + health) / 100
    return max(1, int(round(slots)))