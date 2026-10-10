"""unchecked.py: the statements whose SQL is built at run time, and how
every report lists them -- apart from the findings, counted in nothing."""

import datetime
import io
import json
from pathlib import Path

import jsonschema
import pytest

from ora2pg_gap_report.checklist import read_previous, write_checklist
from ora2pg_gap_report.cli import main
from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.report_generator import to_html, to_json, to_markdown
from ora2pg_gap_report.terminal_report import render as render_terminal
from ora2pg_gap_report.unchecked import Unchecked, find_unchecked

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "docs" / "research" / "samples"


def _sites(source, dialect="oracle"):
    return [(u.line, u.kind, u.partial, u.snippet) for u in find_unchecked(source, dialect)]


ORACLE = """CREATE OR REPLACE PROCEDURE p(t VARCHAR2) IS
  c SYS_REFCURSOR; h INTEGER; n NUMBER;
BEGIN
  EXECUTE IMMEDIATE 'TRUNCATE TABLE x';
  EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM ' || t INTO n;
  EXECUTE IMMEDIATE v_sql USING 1;
  EXECUTE IMMEDIATE build_sql(t, 'a;b') ;
  OPEN c FOR SELECT * FROM dual;
  OPEN c FOR ( SELECT 1 FROM dual );
  OPEN c FOR v_sql USING t;
  OPEN c FOR 'SELECT * FROM ' || t;
  h := DBMS_SQL.OPEN_CURSOR;
  DBMS_SQL.PARSE(h, 'select 1 from dual', DBMS_SQL.NATIVE);
  DBMS_SQL.PARSE(h, q_text, DBMS_SQL.NATIVE);
  FOR r IN (SELECT 1 FROM dual) LOOP NULL; END LOOP;
  -- EXECUTE IMMEDIATE v_comment;
  x := 'EXECUTE IMMEDIATE v_str';
END;
/
"""


def test_oracle_run_time_sql_is_listed_and_literal_sql_is_not():
    assert _sites(ORACLE) == [
        (5, "execute_immediate", True, "EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM ' || t"),
        (6, "execute_immediate", False, "EXECUTE IMMEDIATE v_sql"),
        (7, "execute_immediate", True, "EXECUTE IMMEDIATE build_sql(t, 'a;b')"),
        (10, "open_for", False, "OPEN c FOR v_sql"),
        (11, "open_for", True, "OPEN c FOR 'SELECT * FROM ' || t"),
        (14, "dbms_sql_parse", False, "DBMS_SQL.PARSE(h, q_text, DBMS_SQL.NATIVE)"),
    ]
    assert {u.object_name for u in find_unchecked(ORACLE)} == {"P"}


def test_q_quoted_literals_are_literals():
    source = "BEGIN\n  EXECUTE IMMEDIATE q'[DROP TABLE x]';\n  EXECUTE IMMEDIATE q'{SELECT 1 FROM }' || v INTO n;\nEND;\n"
    assert _sites(source) == [(3, "execute_immediate", True, "EXECUTE IMMEDIATE q'{SELECT 1 FROM }' || v")]


def test_a_long_statement_is_cut():
    source = "BEGIN\n  EXECUTE IMMEDIATE " + " || ".join(f"v_part_{i}" for i in range(20)) + ";\nEND;\n"
    (snippet,) = [u.snippet for u in find_unchecked(source)]
    assert len(snippet) == 80 and snippet.endswith("...")


def test_mysql_prepare():
    source = (
        "CREATE PROCEDURE p() BEGIN\n"
        "  SET @s = CONCAT('SELECT * FROM ', t);\n"
        "  PREPARE st FROM @s;\n"
        "  PREPARE s2 FROM 'SELECT 1';\n"
        "  EXECUTE st;\n"
        "END"
    )
    assert _sites(source, "mysql") == [(3, "prepare", False, "PREPARE st FROM @s")]


def test_mssql_exec_and_sp_executesql():
    source = (
        "CREATE PROCEDURE dbo.p AS\nBEGIN\n"
        " EXEC(@sql)\n"
        " EXEC (N'SELECT 1')\n"
        " EXEC sp_executesql @q, N'@a int', @a = 1;\n"
        " EXECUTE sp_executesql N'SELECT 1'\n"
        " EXEC dbo.other 1\n"
        " EXEC('SELECT * FROM ' + @t)\n"
        "END\n"
    )
    assert _sites(source, "mssql") == [
        (3, "exec", False, "EXEC(@sql)"),
        (5, "sp_executesql", False, "EXEC sp_executesql @q"),
        (8, "exec", True, "EXEC('SELECT * FROM ' + @t)"),
    ]


def test_found_in_logger():
    found = find_unchecked((SAMPLES / "logger.pkb").read_text(encoding="utf-8"))
    assert [(u.object_name, u.line, u.snippet, u.partial) for u in found] == [
        ("LOGGER.F_GET_SET_GLOBAL_CONTEXT", 769, "execute immediate l_sql", False)
    ]


# --- the reports ---------------------------------------------------------------

SITES = [
    Unchecked("execute_immediate", "PKG.RUN", 12, "EXECUTE IMMEDIATE v_sql", False, "pkg.sql"),
    Unchecked("open_for", "PKG.LIST", 30, "OPEN c FOR 'SELECT * FROM ' || t", True, "pkg.sql"),
]
FINDING = Finding("bulk_collect", "high", "PKG.LOAD", 5, "BULK COLLECT", "bulk_collect.bulk_collect", "pkg.sql")


def test_json_lists_them_apart_and_validates():
    schema = json.loads((ROOT / "schemas" / "report.schema.json").read_text(encoding="utf-8"))
    report = json.loads(to_json([FINDING], lang="en", unchecked=SITES))
    jsonschema.validate(report, schema)
    assert report["schema_version"] == 3
    assert len(report["findings"]) == 1
    assert report["unchecked"][1] == {
        "kind": "open_for",
        "object_name": "PKG.LIST",
        "line": 30,
        "snippet": "OPEN c FOR 'SELECT * FROM ' || t",
        "partial": True,
        "source_file": "pkg.sql",
    }
    jsonschema.validate(json.loads(to_json([])), schema)  # always there, empty


def test_markdown_and_html_have_a_section_after_the_findings():
    md = to_markdown([FINDING], lang="en", unchecked=SITES)
    assert md.index("## Not checked: 2 statements with SQL built at run time") > md.index("BULK COLLECT")
    assert "| pkg.sql | `PKG.RUN` | 12 | `EXECUTE IMMEDIATE v_sql` |  |" in md
    assert "| `OPEN c FOR 'SELECT * FROM ' \\|\\| t` | partly |" in md
    html = to_html([FINDING], lang="en", unchecked=SITES)
    assert html.index('id="unchecked"') > html.index("BULK COLLECT")
    assert "OPEN c FOR &#x27;SELECT * FROM &#x27; || t" in html
    assert '"partly" - the string literals' in html.replace("&quot;", '"')


def test_the_partly_note_only_when_one_is_partial():
    md = to_markdown([], lang="en", unchecked=SITES[:1])
    assert "Not checked: 1 statement" in md and "partly" not in md


def test_no_section_without_them():
    assert "Not checked" not in to_markdown([FINDING], lang="en")
    assert 'id="unchecked"' not in to_html([FINDING], lang="en", unchecked=[])


def test_they_count_toward_nothing():
    assert to_markdown([FINDING], lang="en", unchecked=SITES).startswith(to_markdown([FINDING], lang="en").rstrip("\n"))


def _terminal(findings, unchecked):
    from rich.console import Console

    out = io.StringIO()
    render_terminal(findings, console=Console(file=out, width=120, color_system=None), lang="en", unchecked=unchecked)
    return out.getvalue()


def test_terminal_shows_them_with_or_without_findings():
    with_findings = _terminal([FINDING], SITES)
    assert "Not checked: 2 statements with SQL built at run time" in with_findings
    assert "pkg.sql:30" in with_findings and "partly" in with_findings
    alone = _terminal([], SITES)
    assert "No problematic constructs found" in alone and "pkg.sql:12" in alone


# --- the checklist -------------------------------------------------------------

TODAY = datetime.date(2026, 10, 10)


@pytest.fixture
def _in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)


def _checklist(findings, unchecked, previous=None):
    out = io.StringIO()
    write_checklist(
        findings, out, lang="en", previous=previous, scanned_files=["pkg.sql"], version="9.9", today=TODAY, unchecked=unchecked
    )
    return out.getvalue()


def _reread(text):
    path = Path("prev.md")
    path.write_text(text, encoding="utf-8")
    return read_previous(path)


@pytest.mark.usefixtures("_in_tmp")
def test_checklist_boxes_keep_their_ticks_and_stay_out_of_the_progress():
    first = _checklist([FINDING], SITES)
    assert "**Done: 0 of 1 (0 %)**" in first
    assert "## Not checked by the tool: SQL built at run time" in first
    ticked = first.replace("- [ ] `PKG.RUN`", "- [x] `PKG.RUN`")
    second = _checklist([FINDING], SITES, previous=_reread(ticked))
    assert "- [x] `PKG.RUN`" in second and "- [ ] `PKG.LIST`" in second
    assert "**Done: 0 of 1 (0 %)**" in second  # still only the finding
    assert "1 of 2 open" in second


@pytest.mark.usefixtures("_in_tmp")
def test_checklist_with_nothing_found_still_lists_them():
    text = _checklist([], SITES[:1])
    assert "Not checked by the tool" in text and "`PKG.RUN`" in text


@pytest.mark.usefixtures("_in_tmp")
def test_a_statement_gone_from_a_scanned_file_ticks_itself():
    first = _checklist([FINDING], SITES)
    second = _checklist([FINDING], SITES[:1], previous=_reread(first))
    (line,) = [line for line in second.splitlines() if "`PKG.LIST`" in line]
    assert line.startswith("- [x]")


# --- through the CLI -----------------------------------------------------------

SOURCE = """CREATE OR REPLACE PACKAGE BODY pkg AS
  PROCEDURE run(v_sql VARCHAR2) IS
  BEGIN
    EXECUTE IMMEDIATE v_sql;
  END run;
  PROCEDURE other(t VARCHAR2) IS
  BEGIN
    EXECUTE IMMEDIATE 'DELETE FROM ' || t;
  END other;
END pkg;
/
"""


def test_cli_json_and_object_filter(tmp_path, capsys):
    path = tmp_path / "pkg.sql"
    path.write_text(SOURCE, encoding="utf-8")
    assert main(["--format", "json", str(path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert [(u["object_name"], u["line"], u["partial"]) for u in report["unchecked"]] == [
        ("PKG.RUN", 4, False),
        ("PKG.OTHER", 8, True),
    ]
    assert report["findings"] == []
    assert main(["--format", "json", "--object", "other", str(path)]) == 0
    assert [u["object_name"] for u in json.loads(capsys.readouterr().out)["unchecked"]] == ["PKG.OTHER"]


def test_cli_fail_on_ignores_them(tmp_path):
    path = tmp_path / "pkg.sql"
    path.write_text(SOURCE, encoding="utf-8")
    assert main(["--format", "json", "--fail-on", "low", "--output", str(tmp_path / "r.json"), str(path)]) == 0
