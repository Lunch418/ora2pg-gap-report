from ora2pg_gap_report.detectors.collection_type import find_collection_types


def test_table_of_collection_type_is_flagged():
    source = "create type phone_list_t as table of varchar2(20);\n"
    findings = find_collection_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PHONE_LIST_T"
    assert findings[0].severity == "high"


def test_varray_collection_type_is_flagged():
    source = "create type tag_list_t as varray(10) of varchar2(30);\n"
    findings = find_collection_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "TAG_LIST_T"


def test_is_table_of_variant_is_also_flagged():
    # Oracle treats IS and AS interchangeably here, same as everywhere
    # else in PL/SQL type declarations.
    source = "create type phone_list_t is table of varchar2(20);\n"
    findings = find_collection_types(source)
    assert len(findings) == 1


def test_varying_array_synonym_is_flagged():
    # VARYING ARRAY is Oracle's documented synonym for VARRAY in this
    # clause -- same failure mode, must not be a false negative.
    source = "create type tag_list_t as varying array(10) of varchar2(30);\n"
    findings = find_collection_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "TAG_LIST_T"


def test_object_type_is_not_flagged():
    # CREATE TYPE ... AS OBJECT is a different, already-covered gap
    # (object_type.py / GAP-009) -- must not double-count here.
    source = "create type address_t as object (street varchar2(50), city varchar2(50));\n"
    assert find_collection_types(source) == []


def test_local_nested_table_type_declaration_is_not_a_false_positive():
    # 'TYPE t IS TABLE OF ...;' inside a routine's DECLARE section is a
    # different, already-covered gap (bulk_collect.py / GAP-003), not a
    # schema-level CREATE TYPE -- mirrors object_type.py's analogous test.
    source = (
        "create or replace procedure noop as\n"
        "  type t_id_tab is table of number;\n"
        "begin\n"
        "  null;\n"
        "end;\n"
        "/\n"
    )
    assert find_collection_types(source) == []


def test_ordinary_table_is_not_flagged():
    source = "create table orders (order_id number);\n"
    assert find_collection_types(source) == []


def test_real_open_source_utplsql_collection_type_is_flagged():
    # Found scanning utPLSQL (github.com/utPLSQL/utPLSQL) — verbatim
    # excerpt of examples/demo_of_expectations/demo_equal_matcher.sql
    # (the same file as test_object_type.py's matching real-corpus test,
    # which covers this file's two 'AS OBJECT' types; this is its third
    # type declaration, the collection built on top of them).
    source = "create or replace type demo_departments as table of demo_department\n/\n"
    findings = find_collection_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "DEMO_DEPARTMENTS"
