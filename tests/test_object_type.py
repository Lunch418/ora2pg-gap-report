from ora2pg_gap_report.detectors.object_type import find_object_types


def test_type_as_object_and_type_body_are_both_flagged():
    source = """
    create or replace type point_t as object (
      x number,
      y number,
      member function distance_to(p point_t) return number
    );
    /
    create or replace type body point_t as
      member function distance_to(p point_t) return number is
      begin
        return sqrt(power(x - p.x, 2) + power(y - p.y, 2));
      end distance_to;
    end;
    /
    """
    findings = find_object_types(source)
    assert len(findings) == 2
    assert {f.object_name for f in findings} == {"POINT_T"}
    assert {f.snippet for f in findings} == {"CREATE TYPE ... AS OBJECT", "CREATE TYPE BODY"}
    assert {f.severity for f in findings} == {"high"}


def test_local_nested_table_type_declaration_is_not_a_false_positive():
    # 'TYPE t IS TABLE OF ...' (a local collection declaration, already
    # covered by the bulk_collect detector) uses a completely different
    # keyword sequence than 'CREATE TYPE ... AS OBJECT' and must not
    # double-trigger this detector.
    source = """
    create or replace procedure noop as
      type t_id_tab is table of number;
    begin
      null;
    end noop;
    /
    """
    assert find_object_types(source) == []


def test_ordinary_package_without_object_types_is_not_flagged():
    source = """
    create or replace package body plain_pkg as
      procedure noop is
      begin
        null;
      end noop;
    end plain_pkg;
    /
    """
    assert find_object_types(source) == []


def test_is_object_synonym_is_also_matched():
    # Oracle treats IS and AS as interchangeable here, same as everywhere
    # else in PL/SQL declarations.
    source = "create or replace type point_t is object (x number, y number);\n/\n"
    findings = find_object_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "POINT_T"


def test_editionable_modifier_does_not_hide_a_match():
    source = "create or replace editionable type point_t as object (x number);\n/\n"
    findings = find_object_types(source)
    assert len(findings) == 1
    assert findings[0].object_name == "POINT_T"
