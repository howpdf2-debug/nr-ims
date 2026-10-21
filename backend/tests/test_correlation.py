"""Root-cause correlation: pure-function tests (no DB)."""

from app.services.correlation import build_parent_map, find_root_cause

PARENTS = {"IRCA": None, "LKO": "IRCA", "BSB": "LKO", "PRG": "LKO", "MB": "IRCA", "HW": "MB"}


def test_no_upstream_alarm_means_no_root_cause():
    assert find_root_cause("BSB", PARENTS, {"BSB"}) is None


def test_direct_parent_is_root_cause():
    assert find_root_cause("BSB", PARENTS, {"BSB", "LKO"}) == "LKO"


def test_nearest_to_root_ancestor_wins():
    # Both LKO and IRCA are alarming: the top-most one is the real root cause.
    assert find_root_cause("BSB", PARENTS, {"BSB", "LKO", "IRCA"}) == "IRCA"


def test_siblings_do_not_suppress_each_other():
    assert find_root_cause("BSB", PARENTS, {"BSB", "PRG"}) is None


def test_cycle_does_not_loop_forever():
    cyclic = {"A": "B", "B": "C", "C": "A"}
    assert find_root_cause("A", cyclic, {"A", "B"}) == "B"


def test_unknown_station_is_safe():
    assert find_root_cause("ZZZ", PARENTS, {"LKO"}) is None


def test_build_parent_map():
    assert build_parent_map([("A", None), ("B", "A")]) == {"A": None, "B": "A"}
