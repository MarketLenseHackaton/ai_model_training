from marketlens_ai import rank
from tests.sample_places import make_places

W_DEFAULT = {"demand": 3, "health": 2, "affordability": 2}
W_DEMAND_ONLY = {"demand": 3, "health": 1, "affordability": 1}


def test_full_places_are_hidden():
    result = rank(make_places(), W_DEFAULT, "both")
    ranked_ids = [it["id"] for it in result["ranked"]]
    full_ids = [p["id"] for p in result["full"]]
    assert "LAG-FAM-SUP" in full_ids
    assert "LAG-FAM-SUP" not in ranked_ids


def test_sorted_highest_first_and_ranks_numbered():
    result = rank(make_places(), W_DEFAULT, "both")
    totals = [it["scores"]["total"] for it in result["ranked"]]
    assert totals == sorted(totals, reverse=True)
    assert [it["rank"] for it in result["ranked"]] == list(range(1, len(totals) + 1))


def test_fair_share_puts_two_rural_in_top5():
    # demand-heavy weights push rural places down
    without = rank(make_places(), W_DEMAND_ONLY, "cancer", fair_share=False)
    with_fs = rank(make_places(), W_DEMAND_ONLY, "cancer", fair_share=True)

    assert without["equity"]["rural_in_top5"] < 2
    assert with_fs["equity"]["rural_in_top5"] >= 2
    assert with_fs["equity"]["balanced"] is True
    assert any(it["fair_share_added"] for it in with_fs["ranked"][:5])


def test_affordability_high_helps_rural():
    low = rank(make_places(), {"demand": 3, "health": 1, "affordability": 1}, "protein")
    high = rank(make_places(), {"demand": 1, "health": 2, "affordability": 3}, "protein")
    pos_low = next(it["rank"] for it in low["ranked"] if it["id"] == "BAU-HH-VSH")
    pos_high = next(it["rank"] for it in high["ranked"] if it["id"] == "BAU-HH-VSH")
    assert pos_high < pos_low


def test_claim_that_fills_a_place_removes_it():
    places = make_places()
    for p in places:
        if p["id"] == "ABJ-PRO-SUP":
            p["registered"] = p["capacity"]          # last slot taken
    result = rank(places, W_DEFAULT, "both")
    assert "ABJ-PRO-SUP" not in [it["id"] for it in result["ranked"]]


def test_output_shape_matches_contract():
    result = rank(make_places(), W_DEFAULT, "both")
    assert set(result) == {"ranked", "full", "equity", "meta"}
    item = result["ranked"][0]
    assert set(item) == {"rank", "id", "name", "area_type", "is_rural", "segment",
                         "channel", "scores", "confidence", "capacity",
                         "explanation", "labels", "fair_share_added"}
    assert set(item["scores"]) == {"demand", "health", "affordability", "total", "low", "high"}
    assert set(item["capacity"]) == {"registered", "capacity", "slots_left", "status"}