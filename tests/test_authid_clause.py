from ora2pg_gap_report.detectors.authid_clause import find_authid_clauses


def test_authid_current_user_is_flagged():
    source = (
        "CREATE OR REPLACE PROCEDURE run_as_caller\n"
        "  AUTHID CURRENT_USER\n"
        "IS\n"
        "BEGIN\n"
        "  DELETE FROM staging;\n"
        "END;\n"
    )
    findings = find_authid_clauses(source)
    assert len(findings) == 1
    assert findings[0].object_name == "RUN_AS_CALLER"
    assert findings[0].snippet == "AUTHID CURRENT_USER"
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_authid_definer_is_flagged_too():
    # Verified separately: this spelling also makes ora2pg drop the whole
    # routine, so both must be reported.
    source = "CREATE PROCEDURE p\n  AUTHID DEFINER\nIS\nBEGIN\n NULL;\nEND;\n"
    findings = find_authid_clauses(source)
    assert len(findings) == 1
    assert findings[0].snippet == "AUTHID DEFINER"


def test_a_package_level_authid_is_flagged():
    source = "CREATE OR REPLACE PACKAGE p AUTHID CURRENT_USER IS\n  PROCEDURE go;\nEND p;\n"
    assert len(find_authid_clauses(source)) == 1


def test_a_routine_without_the_clause_is_not_flagged():
    source = "CREATE OR REPLACE PROCEDURE p IS\nBEGIN\n  NULL;\nEND;\n"
    assert find_authid_clauses(source) == []


def test_the_word_in_a_comment_is_not_flagged():
    assert find_authid_clauses("-- AUTHID CURRENT_USER was removed\nSELECT 1 FROM dual;\n") == []


def test_real_open_source_utplsql_package_headers_are_flagged():
    # Real shapes from utPLSQL: 38 package specs across the project carry
    # an AUTHID clause, in both spellings, on the CREATE PACKAGE line
    # itself. Every one of them would be dropped from ora2pg's output
    # without a word -- which is what makes this gap worth its severity.
    source = (
        "create or replace noneditionable package ut_runner authid current_user is\n"
        "  procedure run;\n"
        "end;\n"
        "/\n"
        "create or replace noneditionable package ut_trigger_check authid definer is\n"
        "  procedure check_it;\n"
        "end;\n"
    )
    findings = find_authid_clauses(source)
    assert len(findings) == 2
    assert [f.snippet for f in findings] == ["AUTHID CURRENT_USER", "AUTHID DEFINER"]
