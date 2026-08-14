from pathlib import Path

from src.detectors.dbms_utl_calls import find_dbms_utl_calls

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"


def test_flags_unsupported_utl_file_and_dbms_lob_calls_in_file_util_pkg():
    source = (SAMPLES / "file_util_pkg.pkb").read_text()
    findings = find_dbms_utl_calls(source)
    names = {f.object_name for f in findings}

    # Verified against the real file — see git history for the survey.
    assert names == {
        "DBMS_LOB.CREATETEMPORARY",
        "DBMS_LOB.FILECLOSE",
        "DBMS_LOB.FILEISOPEN",
        "DBMS_LOB.FILEOPEN",
        "DBMS_LOB.FILE_READONLY",
        "DBMS_LOB.FREETEMPORARY",
        "DBMS_LOB.LOADFROMFILE",
        "DBMS_LOB.READ",
        "UTL_FILE.FCLOSE",
        "UTL_FILE.FFLUSH",
        "UTL_FILE.FGETATTR",
        "UTL_FILE.FILE_TYPE",
        "UTL_FILE.FOPEN",
        "UTL_FILE.IS_OPEN",
        "UTL_FILE.PUT",
        "UTL_FILE.PUT_RAW",
        "UTL_RAW.CAST_TO_RAW",
    }
    assert all(f.severity == "medium" and f.detector == "dbms_utl_calls" for f in findings)
    # DBMS_LOB.GETLENGTH also appears in this file but has a targeted
    # ora2pg conversion (octet_length()) — must not be reported.
    assert "DBMS_LOB.GETLENGTH" not in names


def test_flags_unsupported_dbms_lob_calls_in_sql_util_pkg_and_ignores_commented_ones():
    source = (SAMPLES / "sql_util_pkg.pkb").read_text()
    findings = find_dbms_utl_calls(source)
    names = {f.object_name for f in findings}

    assert names == {
        "DBMS_LOB.CONVERTTOBLOB",
        "DBMS_LOB.CONVERTTOCLOB",
        "DBMS_LOB.CREATETEMPORARY",
        "DBMS_LOB.DEFAULT_CSID",
        "DBMS_LOB.DEFAULT_LANG_CTX",
        "DBMS_LOB.LOBMAXSIZE",
        "DBMS_LOB.WARN_INCONVERTIBLE_CHAR",
    }
    # DBMS_LOB.OPEN / WRITEAPPEND / LOB_READWRITE and UTL_RAW.LENGTH /
    # CAST_TO_RAW also appear in this file, but only inside a commented-out
    # code block (lines 90-97) — must not be reported as live findings.
    assert "DBMS_LOB.OPEN" not in names
    assert "DBMS_LOB.WRITEAPPEND" not in names
    assert "UTL_RAW.LENGTH" not in names


def test_dbms_output_and_dbms_lob_targeted_conversions_are_not_flagged_in_logger():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = find_dbms_utl_calls(source)
    names = {f.object_name for f in findings}

    assert "DBMS_OUTPUT.PUT_LINE" not in names
    assert "DBMS_OUTPUT.ENABLE" not in names
    # Everything else Logger uses has no targeted conversion.
    assert names == {
        "DBMS_DB_VERSION.VER_LE_10_2",
        "DBMS_SESSION.CLEAR_ALL_CONTEXT",
        "DBMS_SESSION.CLEAR_CONTEXT",
        "DBMS_SESSION.SET_CONTEXT",
        "DBMS_UTILITY.FORMAT_CALL_STACK",
        "DBMS_UTILITY.FORMAT_ERROR_BACKTRACE",
        "DBMS_UTILITY.FORMAT_ERROR_STACK",
        "UTL_LMS.FORMAT_MESSAGE",
    }


def test_no_false_positive_on_source_without_any_dbms_or_utl_reference():
    source = """
    create or replace package body demo as
      procedure foo is
      begin
        null;
      end foo;
    end demo;
    /
    """
    assert find_dbms_utl_calls(source) == []


def test_dollar_prefixed_local_identifier_is_not_mistaken_for_utl_file():
    # A locally-scoped custom type happening to end in "UTL_FILE" must not
    # be parsed as the real UTL_FILE package — \\b alone would treat '$' as
    # a boundary and misfire here.
    source = """
    create or replace package body demo as
      procedure foo is
        v_x my_pkg$utl_file.some_type;
      begin
        null;
      end foo;
    end demo;
    /
    """
    assert find_dbms_utl_calls(source) == []


def test_dollar_and_hash_in_function_name_are_captured_fully():
    source = """
    create or replace package body demo as
      procedure foo is
      begin
        utl_file.put_line$legacy#1(l_file, 'x');
      end foo;
    end demo;
    /
    """
    findings = find_dbms_utl_calls(source)
    assert {f.object_name for f in findings} == {"UTL_FILE.PUT_LINE$LEGACY#1"}
