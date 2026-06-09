import pytest

from delembic.dag import CycleError, topological_sort
from delembic.migration import DataMigration


def _make(revision: str, depends_on: list[str] = []):
    return type(revision, (DataMigration,), {
        "revision": revision,
        "depends_on": depends_on,
        "upgrade": lambda self, conn: None,
    })


def test_empty():
    assert topological_sort({}) == []


def test_single_no_deps():
    m = _make("D001")
    assert topological_sort({"D001": m}) == ["D001"]


def test_linear_chain():
    m1 = _make("D001")
    m2 = _make("D002", ["D001"])
    m3 = _make("D003", ["D002"])
    result = topological_sort({"D001": m1, "D002": m2, "D003": m3})
    assert result == ["D001", "D002", "D003"]


def test_multiple_roots_sorted():
    m1 = _make("D001")
    m2 = _make("D002")
    result = topological_sort({"D001": m1, "D002": m2})
    assert result == ["D001", "D002"]


def test_diamond():
    #   D001
    #  /    \
    # D002  D003
    #  \    /
    #   D004
    m1 = _make("D001")
    m2 = _make("D002", ["D001"])
    m3 = _make("D003", ["D001"])
    m4 = _make("D004", ["D002", "D003"])
    result = topological_sort({"D001": m1, "D002": m2, "D003": m3, "D004": m4})
    assert result.index("D001") < result.index("D002")
    assert result.index("D001") < result.index("D003")
    assert result.index("D002") < result.index("D004")
    assert result.index("D003") < result.index("D004")


def test_cycle_raises():
    m1 = _make("D001", ["D002"])
    m2 = _make("D002", ["D001"])
    with pytest.raises(CycleError):
        topological_sort({"D001": m1, "D002": m2})


def test_external_deps_ignored_in_sort():
    # "abc123" is an Alembic revision — not in migrations dict, should not cause error
    m1 = _make("D001", ["abc123"])
    result = topological_sort({"D001": m1})
    assert result == ["D001"]


def test_external_dep_does_not_affect_order():
    m1 = _make("D001", ["abc123"])
    m2 = _make("D002", ["D001"])
    result = topological_sort({"D001": m1, "D002": m2})
    assert result == ["D001", "D002"]
