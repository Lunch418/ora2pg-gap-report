from ora2pg_gap_report.detectors.temporal_validity import find_temporal_validity


def test_period_for_with_explicit_columns_is_flagged():
    source = (
        "CREATE TABLE emp_hist (\n"
        "    emp_id     NUMBER,\n"
        "    valid_from DATE,\n"
        "    valid_to   DATE,\n"
        "    PERIOD FOR emp_valid_time (valid_from, valid_to)\n"
        ");\n"
    )
    findings = find_temporal_validity(source)
    assert len(findings) == 1
    assert findings[0].object_name == "EMP_HIST"
    assert findings[0].snippet == "PERIOD FOR EMP_VALID_TIME"
    assert findings[0].severity == "high"
    assert findings[0].line == 5


def test_period_for_without_explicit_columns_is_flagged():
    # Oracle generates the hidden boundary columns when they're omitted.
    source = "create table t (id number, period for valid_time);\n"
    findings = find_temporal_validity(source)
    assert len(findings) == 1
    assert findings[0].snippet == "PERIOD FOR VALID_TIME"


def test_a_column_named_period_is_not_flagged():
    source = "CREATE TABLE billing (period NUMBER, amount NUMBER);\n"
    assert find_temporal_validity(source) == []


def test_an_ordinary_table_is_not_flagged():
    source = "CREATE TABLE plain (id NUMBER, note VARCHAR2(50));\n"
    assert find_temporal_validity(source) == []
