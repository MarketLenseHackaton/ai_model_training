from marketlens_ai import equity_overview, discover_plan
from tests.sample_places import make_places


def _place(pid):
    return next(p for p in make_places() if p["id"] == pid)


def test_equity_shape_and_range():
    eq = equity_overview(make_places())
    assert 0 <= eq["score"] <= 100
    assert [a["area"] for a in eq["by_area"]] == ["big_city", "city", "rural"]


def test_no_rural_businesses_means_unfair():
    eq = equity_overview(make_places())          # rural places have 0 businesses
    rural = next(a for a in eq["by_area"] if a["area"] == "rural")
    assert rural["business_pct"] == 0
    assert rural["need_pct"] > 0
    assert eq["score"] < 100


def test_businesses_matching_need_improves_score():
    before = equity_overview(make_places())["score"]

    # spread 10 businesses roughly in line with need:
    # big cities ~60%, other cities ~30%, rural ~10%
    matched = {
        "LAG-FAM-SUP": 4, "ABJ-PRO-SUP": 1, "PHC-YP-RES": 1,   # big cities = 6
        "KAN-FAM-OPM": 1, "KAD-FAM-OPM": 1, "IBD-FAM-SUP": 1,  # cities = 3
        "BAU-HH-VSH": 1, "SOK-HH-WMK": 0,                      # rural = 1
    }
    places = make_places()
    for p in places:
        p["registered"] = matched[p["id"]]

    after = equity_overview(places)["score"]
    assert after > before


def test_too_many_in_one_area_is_unfair_either_way():
    places = make_places()
    for p in places:
        p["registered"] = 5 if p["area_type"] == "rural" else 0
    eq = equity_overview(places)
    assert eq["score"] < 50     # all businesses rural, but most need is not


def test_discover_count_follows_awareness_gap():
    p = _place("BAU-HH-VSH")
    assert len(discover_plan(dict(p, awareness_gap="high"), "protein")["activities"]) == 3
    assert len(discover_plan(dict(p, awareness_gap="medium"), "protein")["activities"]) == 2
    assert len(discover_plan(dict(p, awareness_gap="low"), "protein")["activities"]) == 1


def test_discover_village_starts_with_community_demo():
    plan = discover_plan(dict(_place("BAU-HH-VSH"), awareness_gap="high"), "protein")
    assert plan["activities"][0]["title"] == "Community cooking demo"


def test_discover_message_by_lens():
    p = _place("IBD-FAM-SUP")
    assert discover_plan(p, "protein")["message"] == "Good protein for every pot."
    assert discover_plan(p, "cancer")["message"] == "Add variety to your plate."
    # Ibadan: cancer 70 > protein 58, so "both" leads with variety
    assert discover_plan(p, "both")["message"] == "Add variety to your plate."