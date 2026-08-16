from pathlib import Path

from ora2pg_gap_report.detectors.autonomous_tx import find_autonomous_transactions

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"

# Confirmed by manual inspection of logger.pkb (OraOpenSource/Logger) —
# see docs/research/step0-show-report-baseline.md.
EXPECTED_OBJECTS = {
    "LOGGER.SAVE_GLOBAL_CONTEXT",
    "LOGGER.NULL_GLOBAL_CONTEXTS",
    "LOGGER.LOG_APEX_ITEMS",
    "LOGGER.PURGE",
    "LOGGER.PURGE_ALL",
    "LOGGER.SET_LEVEL",
    "LOGGER.UNSET_CLIENT_LEVEL",
    "LOGGER.INS_LOGGER_LOGS",
}


def test_detects_all_known_occurrences_in_logger_pkb():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = find_autonomous_transactions(source)

    assert {f.object_name for f in findings} == EXPECTED_OBJECTS
    assert len(findings) == len(EXPECTED_OBJECTS)


def test_finding_shape():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = find_autonomous_transactions(source)
    finding = next(f for f in findings if f.object_name == "LOGGER.PURGE_ALL")

    assert finding.detector == "autonomous_tx"
    assert finding.severity == "high"
    assert finding.snippet.lower() == "pragma autonomous_transaction;"
    assert finding.line > 0
    assert "dblink" in finding.message


def test_no_false_positives_on_packages_without_the_pragma():
    for filename in ("sql_util_pkg.pkb", "file_util_pkg.pkb"):
        source = (SAMPLES / filename).read_text()
        assert find_autonomous_transactions(source) == []


def test_ignores_pragma_mentioned_only_in_a_comment():
    source = """
    create or replace package body demo as
      -- note: pragma autonomous_transaction; is NOT actually used here
      procedure noop is
      begin
        null;
      end noop;
    end demo;
    /
    """
    assert find_autonomous_transactions(source) == []


def test_does_not_confuse_pragma_in_one_routine_for_another():
    source = """
    create or replace package body demo as
      procedure with_pragma is
        pragma autonomous_transaction;
      begin
        commit;
      end with_pragma;

      procedure without_pragma is
      begin
        null;
      end without_pragma;
    end demo;
    /
    """
    findings = find_autonomous_transactions(source)
    assert {f.object_name for f in findings} == {"DEMO.WITH_PRAGMA"}


def test_real_open_source_utplsql_test_helper_is_attributed():
    # Found scanning utPLSQL (github.com/utPLSQL/utPLSQL), a real,
    # actively-maintained PL/SQL unit testing framework used in production
    # Oracle shops -- confirms this detector holds up on a genuinely
    # different kind of real-world codebase than the sample/utility
    # corpora used elsewhere in this project's tests. Verbatim excerpt
    # (not paraphrased) of the first 34 lines of
    # test/ut3_tester_helper/main_helper.pkb, closed early with our own
    # 'end main_helper;' -- the real file continues for 178 lines total,
    # this is a representative slice, not the whole thing.
    source = """
    create or replace package body main_helper is

      function get_dbms_output_as_clob return clob is
        l_status number;
        l_line   varchar2(32767);
        l_result clob;
      begin

        dbms_output.get_line(line => l_line, status => l_status);
        if l_status != 1 then
          dbms_lob.createtemporary(l_result, true, dur => dbms_lob.session);
          end if;
        while l_status != 1 loop
          if l_line is not null then
            ut3_develop.ut_utils.append_to_clob(l_result, l_line||chr(10));
            end if;
          dbms_output.get_line(line => l_line, status => l_status);
        end loop;
        return l_result;
      end;

      procedure execute_autonomous(a_sql varchar2) is
        pragma autonomous_transaction;
      begin
        if a_sql is not null then
          execute immediate a_sql;
        end if;
        commit;
      end;

      function run_test(a_path varchar2) return clob is
        l_lines    ut3_develop.ut_varchar2_list;
      begin
        select * bulk collect into l_lines from table(ut3_develop.ut.run(a_path));
        return ut3_develop.ut_utils.table_to_clob(l_lines);
      end;

    end main_helper;
    /
    """
    findings = find_autonomous_transactions(source)
    assert len(findings) == 1
    assert findings[0].object_name == "MAIN_HELPER.EXECUTE_AUTONOMOUS"
