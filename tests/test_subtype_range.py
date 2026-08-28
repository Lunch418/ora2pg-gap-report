from ora2pg_gap_report.detectors.subtype_range import find_subtype_ranges


def test_a_range_constrained_subtype_is_flagged():
    source = (
        "CREATE OR REPLACE PACKAGE types_pkg IS\n"
        "  SUBTYPE small_int IS PLS_INTEGER RANGE 1 .. 100;\n"
        "END types_pkg;\n"
    )
    findings = find_subtype_ranges(source)
    assert len(findings) == 1
    assert findings[0].snippet == "SUBTYPE SMALL_INT ... RANGE 1 .. 100"
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_a_negative_lower_bound_is_captured():
    source = "SUBTYPE temp_c IS PLS_INTEGER RANGE -50 .. 60;\n"
    assert find_subtype_ranges(source)[0].snippet.endswith("RANGE -50 .. 60")


def test_an_unconstrained_subtype_is_not_flagged():
    # Converts to a plain CREATE DOMAIN that loads correctly.
    assert find_subtype_ranges("SUBTYPE small_int IS PLS_INTEGER;\n") == []


def test_a_not_null_subtype_is_not_flagged():
    # Becomes a valid `CREATE DOMAIN ... NOT NULL` -- verified in the
    # same ora2pg run as the RANGE case, which did fail.
    assert find_subtype_ranges("SUBTYPE short_name IS VARCHAR2(30) NOT NULL;\n") == []


def test_the_package_from_the_research_doc_flags_only_the_range_subtype():
    source = (
        "CREATE OR REPLACE PACKAGE types_pkg IS\n"
        "  SUBTYPE small_int IS PLS_INTEGER RANGE 1 .. 100;\n"
        "  SUBTYPE short_name IS VARCHAR2(30) NOT NULL;\n"
        "END types_pkg;\n"
    )
    findings = find_subtype_ranges(source)
    assert len(findings) == 1
    assert findings[0].line == 2


def test_real_open_source_utplsql_subtypes_are_flagged():
    # Real shape from utPLSQL (source/core/ut_utils.pks): range-bounded
    # subtypes used as a poor man's enum.
    source = (
        "  subtype t_test_result   is pls_integer range 0 .. 3;\n"
        "  subtype t_rollback_type is pls_integer range 0 .. 1;\n"
    )
    findings = find_subtype_ranges(source)
    assert len(findings) == 2
    assert findings[0].snippet == "SUBTYPE T_TEST_RESULT ... RANGE 0 .. 3"
