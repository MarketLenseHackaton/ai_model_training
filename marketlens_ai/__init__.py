"""
MarketLens AI module.
Same function names and return shapes as the Project Spec, Section 5.
All functions are real: health_score, total_score, status, suggest_capacity,
rank, simulate, explain, equity_overview, discover_plan.
"""

from .scoring import health_score, total_score, status, suggest_capacity
from .ranking import rank
from .simulate import simulate
from .explain import explain
from .plan import equity_overview, discover_plan

__all__ = [
    "rank", "health_score", "total_score", "status", "simulate", "explain",
    "suggest_capacity", "equity_overview", "discover_plan",
]