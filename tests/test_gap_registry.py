from ora2pg_gap_report.gap_registry import (
    GAPS,
    gap_by_detector,
    gap_by_number,
    normalize_gap_number,
    research_doc_path,
    research_doc_url,
)


def test_registry_has_28_entries_with_unique_numbers_and_detectors():
    assert len(GAPS) == 28
    assert len({g.number for g in GAPS}) == 28
    assert len({g.detector for g in GAPS}) == 28


def test_registry_numbers_are_zero_padded_and_contiguous():
    assert [g.number for g in GAPS] == [f"{i:03d}" for i in range(1, 29)]


def test_normalize_gap_number_accepts_several_shapes():
    assert normalize_gap_number("GAP-023") == "023"
    assert normalize_gap_number("gap-23") == "023"
    assert normalize_gap_number("023") == "023"
    assert normalize_gap_number("23") == "023"
    assert normalize_gap_number("GAP23") == "023"


def test_normalize_gap_number_rejects_garbage():
    assert normalize_gap_number("banana") is None
    assert normalize_gap_number("") is None
    assert normalize_gap_number("GAP-") is None


def test_gap_by_number_round_trips_every_registered_gap():
    for gap in GAPS:
        assert gap_by_number(gap.number) is gap


def test_gap_by_number_unknown_returns_none():
    assert gap_by_number("999") is None


def test_gap_by_detector_round_trips_every_registered_gap():
    for gap in GAPS:
        assert gap_by_detector(gap.detector) is gap


def test_gap_by_detector_unknown_returns_none():
    assert gap_by_detector("not_a_real_detector") is None


def test_research_doc_path_resolves_to_a_real_file_for_every_gap():
    # This project's own repo is a source checkout, so every registered
    # gap's doc must actually be found here -- a gap in GAPS with no
    # matching docs/research/gap-NNN-<slug>.md would be exactly the kind
    # of registry drift this module (and scripts/doctor.py) exists to
    # catch.
    for gap in GAPS:
        path = research_doc_path(gap)
        assert path is not None, f"missing research doc for {gap.number} ({gap.slug})"
        assert path.is_file()


def test_research_doc_url_is_constructible_without_the_file_existing():
    fake = gap_by_number("023")
    url = research_doc_url(fake)
    assert url == (
        "https://github.com/Lunch418/ora2pg-gap-report/blob/main/"
        "docs/research/gap-023-oracle-text.md"
    )


def test_every_gap_has_a_non_empty_version_stamp():
    # ora2pg_version/postgresql_version default to "25.0"/"16" on GapEntry
    # (every gap confirmed so far used the same two versions -- see
    # docs/research/AUDIT.md), but the fields themselves are real strings
    # any future gap could override, not decorative -- --explain prints
    # them (cli.py's _handle_explain()) and scripts/doctor.py cross-checks
    # them against docs/research/GAP_REGISTRY.md's own columns.
    for gap in GAPS:
        assert gap.ora2pg_version
        assert gap.postgresql_version
