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


def test_the_get_ddl_spelling_is_flagged_too():
    # DBMS_METADATA.GET_DDL writes the period as a separate ALTER TABLE
    # after the CREATE TABLE (verbatim from a live Oracle 23ai export).
    # ora2pg drops that statement without a word -- verified on the
    # exported file -- so the period is lost silently rather than breaking
    # the load, and the finding says so with its own message.
    from ora2pg_gap_report.detectors.temporal_validity import find_temporal_validity

    source = (
        '  CREATE TABLE "G045"."EMP_HIST" \n'
        '   (\t"EMP_ID" NUMBER, \n\t"VALID_FROM" DATE, \n\t"VALID_TO" DATE\n'
        '   ) SEGMENT CREATION DEFERRED \n'
        '  ALTER TABLE "G045"."EMP_HIST" ADD PERIOD FOR "EMP_VALID_TIME"("VALID_FROM","VALID_TO") \n'
    )
    findings = find_temporal_validity(source)
    assert [(f.object_name, f.line, f.message_id) for f in findings] == [
        ("EMP_HIST", 6, "temporal_validity.alter")
    ]


def test_an_alter_table_without_a_period_is_not_flagged():
    from ora2pg_gap_report.detectors.temporal_validity import find_temporal_validity

    source = 'ALTER TABLE "HR"."T" ADD CONSTRAINT pk PRIMARY KEY (id);\nALTER TABLE t ADD period NUMBER;\n'
    assert find_temporal_validity(source) == []
