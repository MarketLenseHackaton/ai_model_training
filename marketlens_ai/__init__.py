"""
MarketLens AI module.
Same function names and return shapes as the Project Spec, Section 5.
Real so far: health_score, total_score, status, suggest_capacity.
Still stub: rank, equity_overview, discover_plan.
"""

from .scoring import health_score, total_score, status, suggest_capacity

EXAMPLE_RANK = {
    "ranked": [
        {
            "rank": 1,
            "id": "KAN-FAM-OPM",
            "name": "Kano",
            "area_type": "city",
            "is_rural": False,
            "segment": "Families",
            "channel": "open_market",
            "scores": {"demand": 75, "health": 56, "affordability": 78,
                       "total": 70, "low": 62, "high": 77},
            "confidence": {"pct": 80, "label": "high"},
            "capacity": {"registered": 3, "capacity": 6,
                         "slots_left": 3, "status": "open"},
            "explanation": {
                "demand": "Many families already buy awara and beans.",
                "health": "High protein deficiency reported; no cancer registry here.",
                "affordability": "Beef and chicken cost far more than the national average.",
                "uncertain": "Protein deficiency is scaled from a national survey.",
                "test_first": "Sell 50 trial packs at 2 market stalls for 2 weeks.",
            },
            "labels": {"demand": "estimated", "health": "estimated",
                       "affordability": "measured"},
            "fair_share_added": False,
        }
    ],
    "full": [
        {"id": "LAG-FAM-SUP", "name": "Lagos", "segment": "Families",
         "registered": 8, "capacity": 8}
    ],
    "equity": {"rural_in_top5": 1, "target": 2, "balanced": False},
    "meta": {"n_simulations": 1000, "seed": 42,
             "data_as_of": "2026-03", "lens": "both"},
}


def rank(places, weights, lens, fair_share=False, n_sims=1000, seed=42):
    return EXAMPLE_RANK


def equity_overview(places):
    return {"score": 50, "by_area": []}


def discover_plan(place, lens):
    return {"message": "Good protein for every pot.", "activities": []}


__all__ = [
    "rank", "health_score", "total_score", "status",
    "suggest_capacity", "equity_overview", "discover_plan",
]