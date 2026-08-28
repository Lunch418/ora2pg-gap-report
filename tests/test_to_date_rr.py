from ora2pg_gap_report.detectors.to_date_rr import find_to_date_rr


def test_to_date_with_an_rr_format_is_flagged():
    source = "SELECT TO_DATE('85-06-01', 'RR-MM-DD') FROM dual;\n"
    findings = find_to_date_rr(source)
    assert len(findings) == 1
    assert findings[0].severity == "high"
    assert "TO_DATE" in findings[0].snippet


def test_the_rrrr_spelling_is_flagged_too():
    # Verified: PostgreSQL returns 0001-06-01 BC for RRRR as well.
    assert len(find_to_date_rr("SELECT TO_DATE('1985-06-01','RRRR-MM-DD') FROM dual;\n")) == 1


def test_to_timestamp_is_covered():
    assert len(find_to_date_rr("SELECT TO_TIMESTAMP(s, 'RR-MM-DD HH24:MI') FROM t;\n")) == 1


def test_a_yyyy_format_is_not_flagged():
    assert find_to_date_rr("SELECT TO_DATE('1985-06-01', 'YYYY-MM-DD') FROM dual;\n") == []


def test_a_yy_format_is_not_flagged():
    assert find_to_date_rr("SELECT TO_DATE(s, 'YY-MM-DD') FROM t;\n") == []


def test_to_char_with_rr_is_not_flagged():
    # ora2pg rewrites RR to YY inside TO_CHAR, and on output the two are
    # equivalent anyway -- the pivot rule only applies when parsing.
    assert find_to_date_rr("SELECT TO_CHAR(hired, 'RR') FROM employees;\n") == []


def test_a_bare_rr_in_an_unrelated_string_is_not_flagged():
    assert find_to_date_rr("SELECT 'RR' AS code FROM dual;\n") == []


def test_a_commented_out_call_is_not_flagged():
    assert find_to_date_rr("-- TO_DATE('85-06-01','RR-MM-DD')\nSELECT 1 FROM dual;\n") == []


def test_real_oracle_sample_schema_order_entry_insert_is_flagged():
    # Real shape from Oracle's own db-sample-schemas
    # (order_entry/pord_v3.sql): the format model sits on the line after
    # the value, so the match has to span lines. 211 occurrences of this
    # shape were found across the corpus -- every one of them would import
    # as year 1 BC without raising anything.
    source = (
        "INSERT INTO orders VALUES (2458\n"
        "\t,TO_TIMESTAMP('16-AUG-07 02.34.12.234359 PM'\n"
        "\t,'DD-MON-RR HH.MI.SS.FF AM'\n"
        "\t,'NLS_DATE_LANGUAGE=American')\n"
        "\t,'direct'\n"
        ");\n"
    )
    findings = find_to_date_rr(source)
    assert len(findings) == 1
    assert findings[0].line == 2
