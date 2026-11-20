import re
from marketlens_ai import explain, rank
from tests.sample_places import make_places

W = {"demand": 3, "health": 2, "affordability": 2}
HIGH = {"pct": 82, "label": "high"}
LOW = {"pct": 20, "label": "low"}


def _place(pid):
    return next(p for p in make_places() if p["id"] == pid)


def test_has_all_five_fields():
    e = explain(_place("KAN-FAM-OPM"), "both", HIGH)
    assert set(e) == {"demand", "health", "affordability", "uncertain", "test_first"}
    assert all(isinstance(v, str) and v for v in e.values())


def test_missing_cancer_data_is_said_honestly():
    e = explain(_place("KAN-FAM-OPM"), "cancer", HIGH)
    assert "No colorectal cancer data" in e["health"]
    assert "counts as zero" in e["uncertain"]


def test_protein_lens_mentions_protein_only():
    e = explain(_place("KAN-FAM-OPM"), "protein", HIGH)
    assert "protein deficiency" in e["health"]
    assert "cancer" not in e["health"]


def test_expensive_meat_sentence():
    e = explain(_place("BAU-HH-VSH"), "protein", HIGH)
    assert "far more expensive" in e["affordability"]


def test_assumed_inputs_are_listed():
    e = explain(_place("BAU-HH-VSH"), "protein", HIGH)
    assert "Team assumptions: demand" in e["uncertain"]
    

def test_test_first_by_channel_and_low_confidence():
    assert "market stalls" in explain(_place("KAN-FAM-OPM"), "both", HIGH)["test_first"]
    assert "20-person tasting" in explain(_place("KAN-FAM-OPM"), "both", LOW)["test_first"]


def test_no_cure_or_prevent_claims():
    result = rank(make_places(), W, "both")
    for item in result["ranked"]:
        text = " ".join(item["explanation"].values()).lower()
        assert "cure" not in text and "prevent" not in text


def test_only_numbers_used_are_the_confidence():
    e = explain(_place("IBD-FAM-SUP"), "both", HIGH)
    numbers = set(re.findall(r"\d+", " ".join(e.values())))
    assert numbers <= {"82", "1", "000", "5", "2", "20", "50"}