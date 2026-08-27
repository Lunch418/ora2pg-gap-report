from ora2pg_gap_report.detectors.match_recognize import find_match_recognize


def test_match_recognize_is_flagged_in_a_view():
    source = (
        "CREATE OR REPLACE VIEW v_price_runs AS\n"
        "SELECT *\n"
        "FROM ticker_prices\n"
        "MATCH_RECOGNIZE (\n"
        "  PARTITION BY symbol\n"
        "  ORDER BY price_date\n"
        "  MEASURES STRT.price_date AS start_date\n"
        "  ONE ROW PER MATCH\n"
        "  PATTERN (STRT UP+)\n"
        "  DEFINE UP AS UP.price > PREV(UP.price)\n"
        ");\n"
    )
    findings = find_match_recognize(source)
    assert len(findings) == 1
    assert findings[0].object_name == "V_PRICE_RUNS"
    assert findings[0].snippet == "MATCH_RECOGNIZE"
    assert findings[0].severity == "high"
    assert findings[0].line == 4


def test_match_recognize_is_flagged_inside_a_package_body():
    source = (
        "create or replace package body analytics_pkg as\n"
        "  procedure find_runs is\n"
        "  begin\n"
        "    select count(*) into v_n from prices\n"
        "    match_recognize (\n"
        "      partition by sym pattern (a b) define b as b.p > a.p\n"
        "    );\n"
        "  end find_runs;\n"
        "end analytics_pkg;\n"
        "/\n"
    )
    findings = find_match_recognize(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ANALYTICS_PKG.FIND_RUNS"


def test_a_column_named_match_recognize_is_not_flagged():
    # A bare identifier is legal Oracle and is not the clause -- only the
    # keyword immediately followed by '(' is.
    source = "CREATE TABLE t (match_recognize NUMBER, other VARCHAR2(10));\n"
    assert find_match_recognize(source) == []


def test_match_recognize_inside_a_comment_is_not_flagged():
    source = "-- MATCH_RECOGNIZE ( pattern stuff )\nSELECT 1 FROM dual;\n"
    assert find_match_recognize(source) == []
