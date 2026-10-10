"""The fast paths that keep a large dump's scan linear give the same
answers as the plain ones they replaced."""

import re

from ora2pg_gap_report.detector_spec import _required_word
from ora2pg_gap_report.detectors.supplied_package_call import find_supplied_package_call
from ora2pg_gap_report.plsql_lex import enclosing_object_name, enclosing_object_name_index, mask_strings_and_comments


def test_a_call_after_a_long_comment_is_still_at_a_statement_start():
    comment = "/* " + "x" * 500 + " */"
    source = f"CREATE OR REPLACE PROCEDURE p IS BEGIN NULL; {comment}\n  DBMS_STATS.GATHER_SCHEMA_STATS(USER);\nEND;\n/\n"
    assert [f.snippet for f in find_supplied_package_call(source)] == ["DBMS_STATS.GATHER_SCHEMA_STATS"]


def test_sys_qualified_and_mid_name_occurrences():
    source = (
        "BEGIN\n  SYS.DBMS_APPLICATION_INFO.SET_MODULE('m', NULL);\n"
        "  x := my_pkg.dbms_like(1);\n  v := DBMS_RANDOM.VALUE;\n  XDBMS_A.b(1);\nEND;\n"
    )
    assert [f.snippet for f in find_supplied_package_call(source)] == ["DBMS_APPLICATION_INFO.SET_MODULE"]


def test_the_required_word_comes_only_from_parts_every_match_has():
    assert _required_word(re.compile(r"\bINVISIBLE\b(?!\s*[,)])", re.IGNORECASE)) == "INVISIBLE"
    assert _required_word(re.compile(r"\bREAD\s+ONLY\b", re.IGNORECASE)) == "READ"
    assert _required_word(re.compile(r"\b(PIVOT|UNPIVOT)\b")) is None  # an alternative: no one word
    assert _required_word(re.compile(r"(?:MDSYS\s*\.\s*)?SDO_GEOMETRY\b")) == "SDO_GEOMETRY"  # not the optional MDSYS
    assert _required_word(re.compile(r"\bAS\s*\(")) is None  # too short to be worth it


def _naive(index, position):
    package_name, leaf = None, None
    for pos, kind, name in index:
        if pos > position:
            break
        if kind == "end":
            package_name, leaf = None, None
        elif kind == "package":
            package_name, leaf = name, None
        else:
            if kind != "nested_routine":
                package_name = None
            leaf = (name, kind == "nested_routine")
    if leaf:
        return f"{package_name}.{leaf[0]}" if leaf[1] and package_name else leaf[0]
    return package_name or "UNKNOWN"


def test_the_object_name_lookup_agrees_with_walking_the_index():
    source = (
        "CREATE OR REPLACE PACKAGE BODY p AS\n  PROCEDURE a IS BEGIN NULL; END;\n  FUNCTION b RETURN NUMBER IS BEGIN RETURN 1; END;\nEND p;\n/\n"
        "SELECT 1 FROM dual;\nCREATE OR REPLACE PROCEDURE q IS BEGIN NULL; END;\n/\n"
        "CREATE OR REPLACE TRIGGER t BEFORE INSERT ON x BEGIN NULL; END;\n/\n"
    )
    index = enclosing_object_name_index(mask_strings_and_comments(source))
    for position in range(len(source) + 1):
        assert enclosing_object_name(index, position) == _naive(index, position), position
