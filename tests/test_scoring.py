import pytest
from marketlens_ai import health_score, total_score, status, suggest_capacity

KANO = {
    "demand": 75, "protein_deficiency": 82, "crc_index": None,
    "meat_cost": 78, "capacity": 6, "registered": 3, "population": 4_910_000,
}
IBADAN = {
    "demand": 66, "protein_deficiency": 58, "crc_index": 70,
    "meat_cost": 64, "capacity": 5, "registered": 2, "population": 3_600_000,
}


def test_health_protein_lens():
    assert health_score(KANO, "protein") == 82


def test_health_cancer_lens_missing_data_is_zero():
    assert health_score(KANO, "cancer") == 0


def test_health_both_uses_only_available_values():
    assert health_score(KANO, "both") == 82          # cancer missing
    assert health_score(IBADAN, "both") == 64        # (58 + 70) / 2


def test_bad_lens_raises():
    with pytest.raises(ValueError):
        health_score(KANO, "vegan")


def test_total_equal_weights_is_plain_average():
    w = {"demand": 1, "health": 1, "affordability": 1}
    assert total_score(IBADAN, w, "both") == round((66 + 64 + 64) / 3)


def test_total_kano_example():
    w = {"demand": 3, "health": 2, "affordability": 2}
    # health for Kano with lens "both" = 82 (no cancer data)
    assert total_score(KANO, w, "both") == round((75*3 + 82*2 + 78*2) / 7)


def test_higher_affordability_weight_helps_expensive_meat():
    low = total_score(KANO, {"demand": 2, "health": 2, "affordability": 1}, "protein")
    high = total_score(KANO, {"demand": 2, "health": 2, "affordability": 3}, "protein")
    assert high >= low


def test_bad_weight_raises():
    with pytest.raises(ValueError):
        total_score(KANO, {"demand": 5, "health": 2, "affordability": 2}, "both")


def test_status_rules():
    assert status({"capacity": 6, "registered": 3}) == "open"
    assert status({"capacity": 5, "registered": 4}) == "nearly_full"   # 80%
    assert status({"capacity": 8, "registered": 8}) == "full"
    assert status({"capacity": 0, "registered": 0}) == "full"


def test_suggest_capacity_at_least_one():
    assert suggest_capacity({"population": 0, "demand": 0}) == 1
    assert suggest_capacity(KANO) >= 1