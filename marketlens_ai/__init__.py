"""
MarketLens AI module.
Same function names and return shapes as the Project Spec, Section 5.
Real so far: health_score, total_score, status, suggest_capacity, rank,
             confidence + score range (simulate).
Still stub: equity_overview, discover_plan. Placeholder: explanation text.
"""

from .scoring import health_score, total_score, status, suggest_capacity
from .ranking import rank
from .simulate import simulate


def equity_overview(places):
    return {"score": 50, "by_area": []}


def discover_plan(place, lens):
    return {"message": "Good protein for every pot.", "activities": []}


__all__ = [
    "rank", "health_score", "total_score", "status", "simulate",
    "suggest_capacity", "equity_overview", "discover_plan",
]