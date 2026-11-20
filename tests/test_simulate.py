import time
from marketlens_ai import simulate, rank
from tests.sample_places import make_places

W = {"demand": 3, "health": 2, "affordability": 2}


def _open(places):
    return [p for p in places if p["registered"] < p["capacity"]]


def test_same_seed_same_result():
    places = _open(make_places())
    assert simulate(places, W, "both", seed=42) == simulate(places, W, "both", seed=42)


def test_pct_between_0_and_100_and_labels_match():
    result = simulate(_open(make_places()), W, "both")
    for r in result.values():
        assert 0 <= r["pct"] <= 100
        expected = "high" if r["pct"] >= 70 else "medium" if r["pct"] >= 40 else "low"
        assert r["label"] == expected
        assert r["low"] <= r["high"]


def test_fewer_than_five_places_all_100_percent():
    places = _open(make_places())[:3]
    for r in simulate(places, W, "both").values():
        assert r["pct"] == 100


def test_assumed_data_gives_wider_range():
    base = {"demand": 60, "protein_deficiency": 60, "crc_index": None, "meat_cost": 60,
            "capacity": 5, "registered": 0}
    measured = dict(base, id="M", label_demand="measured",
                    label_health="measured", label_meat_cost="measured")
    assumed = dict(base, id="A", label_demand="assumed",
                   label_health="assumed", label_meat_cost="assumed")
    r = simulate([measured, assumed], W, "protein")
    width_measured = r["M"]["high"] - r["M"]["low"]
    width_assumed = r["A"]["high"] - r["A"]["low"]
    assert width_assumed > width_measured


def test_rank_uses_real_confidence():
    result = rank(make_places(), W, "both")
    pcts = {it["confidence"]["pct"] for it in result["ranked"]}
    assert pcts != {50}     # no longer the placeholder


def test_fast_enough():
    places = []
    for i in range(20):
        p = dict(make_places()[i % 8])
        p["id"] = f"P{i}"
        p["registered"] = 0
        places.append(p)
    start = time.perf_counter()
    rank(places, W, "both", n_sims=1000)
    assert time.perf_counter() - start < 2.0