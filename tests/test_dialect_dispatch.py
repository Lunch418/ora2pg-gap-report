"""Dialect plumbing shared by --dialect, --verify and --fix.

The pieces tested here are what keeps a scan, the snapshot it writes and
the verification of that snapshot all talking about the same dialect
without the baseline file ever having to record one.
"""

import pytest

from ora2pg_gap_report.core import (
    DIALECTS,
    baseline_dialects,
    detector_names,
    dialect_of_detector,
)


def test_dialects_is_derived_from_the_detector_registry():
    # Not a separately typed-out tuple: adding a dialect to
    # _DETECTORS_BY_DIALECT must be enough for the CLI and TUI to offer it.
    assert set(DIALECTS) == {"oracle", "mysql", "mssql"}
    assert DIALECTS[0] == "oracle", "oracle is the default and is presented first"


def test_every_detector_belongs_to_exactly_one_dialect():
    # The whole inference story below rests on this: if one detector name
    # appeared under two dialects, a baseline containing it could not be
    # traced back to the scan that wrote it.
    for dialect in DIALECTS:
        for name in detector_names(dialect):
            others = [d for d in DIALECTS if d != dialect and name in detector_names(d)]
            assert others == [], f"{name} is registered under {dialect} and {others}"


@pytest.mark.parametrize(
    ("detector", "expected"),
    [
        ("bulk_collect", "oracle"),
        ("dbms_utl_calls", "oracle"),  # a real detector with no GAP-NNN of its own
        ("mysql_key_index", "mysql"),
        ("mssql_bracket_identifier", "mssql"),
    ],
)
def test_dialect_of_detector(detector, expected):
    assert dialect_of_detector(detector) == expected


def test_dialect_of_an_unknown_detector_is_none():
    assert dialect_of_detector("no_such_detector_anywhere") is None


def _baseline(*detectors):
    return [{"detector": d, "group_key": f"k{i}"} for i, d in enumerate(detectors)]


def test_baseline_dialect_is_inferred_from_its_detector_names():
    dialects, unknown = baseline_dialects(_baseline("mysql_key_index", "mysql_signal"))
    assert dialects == {"mysql"}
    assert unknown == ()


def test_an_oracle_baseline_written_before_dialects_existed_still_resolves():
    # The backward-compatibility guarantee: no schema bump was needed for
    # dialects, so a snapshot from an older build carries no dialect field
    # and must still be traced back through its detector names alone.
    dialects, unknown = baseline_dialects(_baseline("bulk_collect", "database_link"))
    assert dialects == {"oracle"}
    assert unknown == ()


def test_an_empty_baseline_yields_no_dialect_rather_than_guessing():
    assert baseline_dialects([]) == (frozenset(), ())


def test_a_hand_merged_baseline_reports_every_dialect_it_mixes():
    dialects, unknown = baseline_dialects(_baseline("bulk_collect", "mysql_signal"))
    assert dialects == {"oracle", "mysql"}
    assert unknown == ()


def test_detectors_this_build_does_not_have_are_reported_not_dropped():
    # A snapshot from a newer version. Silently ignoring the unknown names
    # would let --verify report a confident result computed from a subset
    # of the baseline.
    dialects, unknown = baseline_dialects(_baseline("mysql_signal", "from_the_future", "also_new"))
    assert dialects == {"mysql"}
    assert unknown == ("also_new", "from_the_future")
