from ora2pg_gap_report.detectors.object_table import find_object_tables


def test_object_table_is_flagged():
    source = (
        "CREATE TABLE person_objs OF person_typ (\n"
        "    person_id PRIMARY KEY\n"
        ");\n"
    )
    findings = find_object_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PERSON_OBJS"
    assert findings[0].snippet == "OF PERSON_TYP"
    assert findings[0].severity == "high"


def test_object_table_without_a_constraint_list_is_flagged():
    source = "create table addresses of address_typ;\n"
    findings = find_object_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ADDRESSES"


def test_schema_qualified_type_is_captured():
    source = "CREATE TABLE hr.people OF hr.person_typ;\n"
    findings = find_object_tables(source)
    assert len(findings) == 1
    assert findings[0].snippet == "OF HR.PERSON_TYP"


def test_an_ordinary_table_with_a_column_starting_with_of_is_not_flagged():
    # `OF` only makes it an object table directly after the table name --
    # a column list always opens with '(' first.
    source = "CREATE TABLE plain (id NUMBER, of_note VARCHAR2(10));\n"
    assert find_object_tables(source) == []


def test_a_create_table_as_select_is_not_flagged():
    source = "CREATE TABLE snapshot_t AS SELECT * FROM source_t;\n"
    assert find_object_tables(source) == []


def test_real_utplsql_object_table_line_points_at_the_of_keyword_not_create_table():
    # Real shape from utPLSQL's source/core/ut_suite_cache.sql: a licence
    # comment sits between `create table` and `of <type>`. The reported
    # line must point at the OF keyword (where the construct actually is),
    # not at the CREATE TABLE line 13 lines earlier -- masking blanks the
    # comment, so a naive match-start line number lands on the wrong one.
    source = (
        "create table ut_suite_cache \n"
        "  /*\n"
        "  utPLSQL - Version 3\n"
        "  Copyright 2016 - 2021 utPLSQL Project\n"
        "  Licensed under the Apache License, Version 2.0\n"
        "  */\n"
        "  of ut_suite_cache_row\n"
        ";\n"
    )
    findings = find_object_tables(source)
    assert len(findings) == 1
    assert findings[0].object_name == "UT_SUITE_CACHE"
    assert findings[0].line == 7
