from pathlib import Path

from ora2pg_gap_report.detectors.dbms_utl_calls import find_dbms_utl_calls
from ora2pg_gap_report.detectors.supplied_package_call import find_supplied_package_call

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_120_123"
SAMPLES = Path(__file__).parents[1] / "docs" / "research" / "samples"


def _names(source):
    return [f.snippet for f in find_supplied_package_call(source)]


def test_supplied_procedures_called_as_statements_are_flagged():
    assert _names((FIXTURES / "calls_source.sql").read_text(encoding="utf-8")) == [
        "DBMS_APPLICATION_INFO.SET_MODULE",
        "DBMS_APPLICATION_INFO.SET_ACTION",
        "DBMS_STATS.GATHER_TABLE_STATS",
        "DBMS_SCHEDULER.RUN_JOB",
        "UTL_FILE.FCLOSE_ALL",
        "HTP.P",
        "OWA_UTIL.MIME_HEADER",
        "DBMS_UTILITY.EXEC_DDL_STATEMENT",
    ]


def test_dbms_output_disable_is_not_converted_but_enable_is():
    # ora2pg comments out DBMS_OUTPUT.ENABLE, and copies DISABLE.
    assert _names((FIXTURES / "edge_source.sql").read_text(encoding="utf-8")) == [
        "DBMS_OUTPUT.DISABLE",
        "DBMS_APPLICATION_INFO.SET_MODULE",
        "HTP.P",
    ]


def test_logger_htp():
    assert "HTP.P" in _names((SAMPLES / "logger.pkb").read_text(encoding="utf-8"))


def test_converted_calls_functions_and_strings_are_not_flagged():
    source = """CREATE OR REPLACE PROCEDURE p IS
  n NUMBER;
  c INTEGER;
BEGIN
  DBMS_OUTPUT.PUT_LINE('HTP.P(1);');
  DBMS_LOCK.SLEEP(1);
  n := DBMS_RANDOM.VALUE;
  c := DBMS_SQL.OPEN_CURSOR;
  DBMS_SQL.CLOSE_CURSOR(c);
  IF DBMS_LOB.GETLENGTH(NULL) > 0 THEN NULL; END IF;
  -- DBMS_STATS.GATHER_SCHEMA_STATS(USER);
  my_pkg.do_it(1);
END;
/
"""
    assert _names(source) == []


def test_dbms_utl_calls_leaves_statement_calls_to_this_gap():
    source = "BEGIN\n  DBMS_APPLICATION_INFO.SET_MODULE('m', NULL);\n  x := UTL_RAW.LENGTH(y);\nEND;\n"
    assert _names(source) == ["DBMS_APPLICATION_INFO.SET_MODULE"]
    assert [f.object_name for f in find_dbms_utl_calls(source)] == ["UTL_RAW.LENGTH"]
