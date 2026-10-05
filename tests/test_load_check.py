import json
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

from ora2pg_gap_report import load_check
from ora2pg_gap_report.cli import main
from ora2pg_gap_report.load_check import (
    LoadCheckError,
    order_files,
    parse_psql_errors,
    parse_target,
    run_load_check,
)
from ora2pg_gap_report.report_generator import to_load_check_json

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "end-to-end"
SCHEMA = json.loads((ROOT / "schemas" / "load-check.schema.json").read_text(encoding="utf-8"))


# --- a fake psql ------------------------------------------------------------


class FakePsql:
    """Stands in for subprocess.run: answers psql (and docker) the way the
    real ones do, with errors scripted per loaded file.

    `errors` maps a loaded file's *name* to the stderr block psql would
    print for it, with {script} standing for the sanitized copy's path."""

    def __init__(self, errors=None, *, connect=True, finish=True, server="16.4"):
        self.errors = errors or {}
        self.connect = connect
        self.finish = finish
        self.server = server
        self.calls = []
        self.driver = None

    def _psql(self, driver_path, read_script):
        driver = read_script(driver_path)
        self.driver = driver
        if not self.connect:
            return subprocess.CompletedProcess([], 2, b"", b"psql: error: connection refused\n")
        stdout = [f"@@ora2pg-gap-report:server: {self.server}"]
        stderr = []
        script_paths = [line.split("'")[1] for line in driver.splitlines() if line.startswith("\\i ")]
        for script_path in script_paths:
            stdout.append(f"@@ora2pg-gap-report:file:{script_path.rsplit('/', 1)[-1]}")
            text = read_script(script_path)
            for name, block in self.errors.items():
                if f"-- file: {name}\n" in text:
                    stderr.append(block.format(script=script_path))
        if self.finish:
            stdout.append("@@ora2pg-gap-report:done")
        return subprocess.CompletedProcess(
            [], 0, ("\n".join(stdout) + "\n").encode(), ("\n".join(stderr) + "\n").encode()
        )

    def __call__(self, cmd, *, env=None, timeout=None):
        self.calls.append(list(cmd))
        if cmd[0] == "psql":
            driver_path = cmd[cmd.index("-f") + 1]
            return self._psql(driver_path, lambda p: Path(p).read_text(encoding="utf-8", errors="replace"))
        if cmd[0] == "docker":
            verb = cmd[1]
            if verb == "cp":
                self.copied_from = Path(cmd[2].rstrip(".").rstrip("/\\"))
                return subprocess.CompletedProcess([], 0, b"", b"")
            if verb == "exec" and "psql" in cmd:
                driver_path = cmd[cmd.index("-f") + 1]
                local = self.copied_from

                def read(p):
                    return (local / p.rsplit("/", 1)[-1]).read_text(encoding="utf-8", errors="replace")

                return self._psql(driver_path, read)
            return subprocess.CompletedProcess([], 0, b"abc123\n", b"")
        raise AssertionError(f"unexpected command {cmd}")


def _write(tmp_path, name, body):
    path = tmp_path / name
    path.write_text(f"-- file: {name}\n{body}", encoding="utf-8")
    return path


IDENTITY_SQL = "CREATE TABLE t1 (\n  id int GENERATED ALWAYS AS IDENTITY ((START WITH 1)),\n  x int\n);\n"
IDENTITY_ERR = (
    'psql:{script}:5: ERROR:  42601: syntax error at or near "("\n'
    "LINE 2:   id int GENERATED ALWAYS AS IDENTITY ((START WITH 1)),\n"
    "                                              ^\n"
    "LOCATION:  scanner_yyerror, scan.l:1244"
)
BULK_SQL = (
    "\\set ON_ERROR_STOP ON\n"
    "SET check_function_bodies = false;\n"
    "CREATE OR REPLACE PROCEDURE p () AS $body$\n"
    "DECLARE\n"
    "    TYPE t_id_tab IS TABLE OF integer;\n"
    "BEGIN\n"
    "    NULL;\n"
    "END;\n"
    "$body$\n"
    "LANGUAGE PLPGSQL\n"
    ";\n"
)
BULK_ERR = (
    'psql:{script}:12: ERROR:  42601: syntax error at or near "IS"\n'
    "LINE 3:     TYPE t_id_tab IS TABLE OF integer;\n"
    "                          ^\n"
    'CONTEXT:  invalid type name "t_id_tab IS TABLE OF integer"\n'
    "LOCATION:  scanner_yyerror, scan.l:1244"
)
MISC_SQL = "SELECT * FROM missing_tab;\nCREATE INDEX CONCURRENTLY i ON t(x);\nSELECT 1/0;\n"
MISC_ERR = (
    'psql:{script}:2: ERROR:  42P01: relation "missing_tab" does not exist\n'
    "LINE 1: SELECT * FROM missing_tab;\n"
    "psql:{script}:3: ERROR:  25001: CREATE INDEX CONCURRENTLY cannot run inside a transaction block\n"
    "psql:{script}:4: ERROR:  22012: division by zero\n"
    "psql:{script}:4: WARNING:  01000: just a warning"
)


@pytest.fixture
def scripted(tmp_path, monkeypatch):
    files = [
        _write(tmp_path, "a.sql", IDENTITY_SQL),
        _write(tmp_path, "b.sql", BULK_SQL),
        _write(tmp_path, "c.sql", MISC_SQL),
    ]
    fake = FakePsql({"a.sql": IDENTITY_ERR, "b.sql": BULK_ERR, "c.sql": MISC_ERR})
    monkeypatch.setattr(load_check, "_run", fake)
    return files, fake


def test_errors_are_tied_to_statements_lines_and_gaps(scripted):
    files, _ = scripted
    result = run_load_check(files, parse_target("postgresql://u:secret@h/db"))
    got = [(Path(e.file).name, e.line, e.statement_line, e.sqlstate, e.category, e.gap_number) for e in result.errors]
    assert got == [
        ("a.sql", 3, 2, "42601", "fixable", "028"),
        ("b.sql", 6, 4, "42601", "gap", "003"),
        ("c.sql", 2, 2, "42P01", "dependency", None),
        ("c.sql", 3, 3, "25001", "environment", None),
        ("c.sql", 4, 4, "22012", "unknown", None),
    ]
    assert result.failed
    assert result.server_version == "16.4"
    # b.sql's SET check_function_bodies was blanked, so it didn't run.
    assert result.statements == 1 + 1 + 3
    assert result.target == "postgresql://u:***@h/db"
    assert [(Path(f).name, n.kind) for f, n in result.neutralised] == [("b.sql", "meta"), ("b.sql", "setting")]


def test_the_driver_rolls_back_and_forces_function_body_checks(scripted):
    files, fake = scripted
    run_load_check(files, parse_target("dbname=scratch"))
    driver = fake.driver.splitlines()
    assert driver.index("BEGIN;") < driver.index("SET LOCAL check_function_bodies = on;")
    assert driver.index("ROLLBACK;") > max(i for i, line in enumerate(driver) if line.startswith("\\i "))
    assert "\\set ON_ERROR_ROLLBACK on" in driver
    assert not any(line.strip().upper() == "COMMIT;" for line in driver)


def test_the_files_psql_reads_have_nothing_that_could_commit(tmp_path, monkeypatch):
    path = _write(tmp_path, "x.sql", "BEGIN;\nCREATE TABLE t (id int);\nCOMMIT;\n\\connect other\n")
    seen = {}

    def fake(cmd, *, env=None, timeout=None):
        driver = Path(cmd[cmd.index("-f") + 1]).read_text(encoding="utf-8")
        script = [line.split("'")[1] for line in driver.splitlines() if line.startswith("\\i ")][0]
        seen["text"] = Path(script).read_text(encoding="utf-8")
        return subprocess.CompletedProcess(
            [], 0, b"@@ora2pg-gap-report:server: 16\n@@ora2pg-gap-report:done\n", b""
        )

    monkeypatch.setattr(load_check, "_run", fake)
    result = run_load_check([path], parse_target("dbname=scratch"))
    assert "COMMIT" not in seen["text"] and "BEGIN" not in seen["text"] and "\\connect" not in seen["text"]
    assert "CREATE TABLE t (id int);" in seen["text"]
    assert seen["text"].count("\n") == path.read_text(encoding="utf-8").count("\n")
    assert not result.failed


def test_docker_target_removes_the_container_even_when_psql_fails(scripted, monkeypatch):
    files, fake = scripted
    fake.connect = False
    with pytest.raises(LoadCheckError) as exc_info:
        run_load_check(files, parse_target("docker"))
    assert exc_info.value.key == "load_check_connect_failed"
    verbs = [c[1] for c in fake.calls if c[0] == "docker"]
    assert verbs[0] == "run" and verbs[-1] == "rm"
    run_cmd = fake.calls[0]
    assert "postgres:16-alpine" in run_cmd and "-p" not in run_cmd  # no port is published


def test_docker_target_runs_the_check_inside_the_container(scripted):
    files, fake = scripted
    result = run_load_check(files, parse_target("docker:postgres:17"))
    assert result.target == "docker postgres:17"
    assert [e.category for e in result.errors] == ["fixable", "gap", "dependency", "environment", "unknown"]
    assert fake.calls[-1][:3] == ["docker", "rm", "-f"]


def test_missing_psql_and_missing_docker_are_reported(tmp_path, monkeypatch):
    path = _write(tmp_path, "x.sql", "SELECT 1;\n")

    def missing(cmd, *, env=None, timeout=None):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(load_check, "_run", missing)
    with pytest.raises(LoadCheckError) as psql_exc:
        run_load_check([path], parse_target("dbname=x"))
    assert psql_exc.value.key == "load_check_no_psql"
    with pytest.raises(LoadCheckError) as docker_exc:
        run_load_check([path], parse_target("docker"))
    assert docker_exc.value.key == "load_check_no_docker"


def test_a_run_that_stops_halfway_is_not_presented_as_a_result(scripted):
    files, fake = scripted
    fake.finish = False
    with pytest.raises(LoadCheckError) as exc_info:
        run_load_check(files, parse_target("dbname=x"))
    assert exc_info.value.key == "load_check_incomplete"


def test_unterminated_file_is_skipped_not_glued_to_the_next(tmp_path, monkeypatch):
    bad = _write(tmp_path, "bad.sql", "SELECT 'never closed;\n")
    good = _write(tmp_path, "good.sql", "SELECT 1;\n")
    fake = FakePsql()
    monkeypatch.setattr(load_check, "_run", fake)
    result = run_load_check([bad, good], parse_target("dbname=x"))
    assert [Path(f).name for f in result.files] == ["good.sql"]
    assert [(Path(s.file).name, s.reason, s.line) for s in result.skipped_files] == [("bad.sql", "unterminated", 2)]


def test_parse_target():
    assert (parse_target("docker").kind, parse_target("docker").value) == ("docker", "postgres:16-alpine")
    assert parse_target("DOCKER:my/pg:16").value == "my/pg:16"
    dsn = parse_target("host=h dbname=d password='p w' user=u")
    assert dsn.kind == "dsn"
    assert dsn.describe() == "host=h dbname=d password=*** user=u"


def test_parse_psql_errors_reads_translated_severity_and_skips_others():
    stderr = (
        "psql:/tmp/x/0001.sql:7: ОШИБКА:  42601: ошибка синтаксиса (примерное положение: \"(\")\n"
        "СТРОКА 2:   id int\n"
        "ПОДСКАЗКА:  подсказка\n"
        "psql:/tmp/x/driver.sql:6: ERROR:  42501: permission denied to set parameter \"lc_messages\"\n"
        "psql:/tmp/x/0001.sql:9: WARNING:  01000: careful\n"
        "psql:C:/Users/me/x/0002.sql:3: ERROR:  42P01: relation \"t\" does not exist\n"
    )
    errors = parse_psql_errors(stderr, ["0001.sql", "0002.sql"])
    assert [(e.script, e.end_line, e.sqlstate, e.position_line, e.hint) for e in errors] == [
        ("0001.sql", 7, "42601", 2, "подсказка"),
        ("0002.sql", 3, "42P01", None, None),
    ]


def test_directory_files_load_in_ora2pg_type_order(tmp_path):
    root = tmp_path / "out"
    for name in (
        "FKEYS_output.sql",
        "TABLE_output.sql",
        "VIEW_output.sql",
        "aaa_misc.sql",
        "SEQUENCE_output.sql",
        "INDEXES_output.sql",
        "TYPE_output.sql",
    ):
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("SELECT 1;\n", encoding="utf-8")
    nested = root / "schema" / "tables"
    nested.mkdir(parents=True)
    (nested / "orders.sql").write_text("SELECT 1;\n", encoding="utf-8")
    ordered, empty = order_files([root])
    assert empty == []
    assert [p.name for p in ordered] == [
        "TYPE_output.sql",
        "SEQUENCE_output.sql",
        "TABLE_output.sql",
        "orders.sql",
        "VIEW_output.sql",
        "aaa_misc.sql",
        "INDEXES_output.sql",
        "FKEYS_output.sql",
    ]


def test_explicitly_listed_files_keep_their_order(tmp_path):
    a = tmp_path / "z_TABLE.sql"
    b = tmp_path / "a_TYPE.sql"
    for p in (a, b):
        p.write_text("SELECT 1;\n", encoding="utf-8")
    ordered, _ = order_files([a, b, a])
    assert ordered == [a, b]


def test_json_output_matches_its_schema(scripted):
    files, _ = scripted
    result = run_load_check(files, parse_target("dbname=x"))
    payload = json.loads(to_load_check_json(result))
    jsonschema.Draft202012Validator.check_schema(SCHEMA)
    jsonschema.validate(payload, SCHEMA)
    assert payload["counts"] == {"fixable": 1, "gap": 1, "unknown": 1, "dependency": 1, "environment": 1}
    assert payload["failed"] is True


# --- the CLI ----------------------------------------------------------------


def test_cli_exit_code_is_1_when_the_output_does_not_load(scripted, capsys):
    files, _ = scripted
    code = main(["--lang", "en", "--load-check", "dbname=x", *map(str, files)])
    out, err = capsys.readouterr()
    assert code == 1
    assert "GAP-028" in out and "GAP-003" in out
    assert "--fix --write" in out
    assert "doesn't load" in err


def test_cli_exit_code_is_0_when_everything_loads(tmp_path, monkeypatch, capsys):
    path = _write(tmp_path, "ok.sql", "CREATE TABLE t (id int);\n")
    monkeypatch.setattr(load_check, "_run", FakePsql())
    assert main(["--lang", "ru", "--load-check", "dbname=x", str(path)]) == 0
    assert "Всё загрузилось" in capsys.readouterr().out


def test_cli_environment_errors_alone_do_not_fail(tmp_path, monkeypatch, capsys):
    path = _write(tmp_path, "idx.sql", "CREATE INDEX CONCURRENTLY i ON t(x);\n")
    err = "psql:{script}:2: ERROR:  25001: CREATE INDEX CONCURRENTLY cannot run inside a transaction block"
    monkeypatch.setattr(load_check, "_run", FakePsql({"idx.sql": err}))
    assert main(["--lang", "en", "--load-check", "dbname=x", str(path)]) == 0


def test_cli_json_output_to_file(scripted, tmp_path):
    files, _ = scripted
    out = tmp_path / "load.json"
    assert main(["--load-check", "dbname=x", "-f", "json", "-o", str(out), *map(str, files)]) == 1
    jsonschema.validate(json.loads(out.read_text(encoding="utf-8")), SCHEMA)


@pytest.mark.parametrize(
    "extra",
    [["--verify"], ["--fix"], ["--save", "x.json"], ["--fail-on", "high"], ["--severity", "high"], ["-f", "html"]],
)
def test_cli_rejects_combinations(extra, tmp_path, capsys):
    path = _write(tmp_path, "x.sql", "SELECT 1;\n")
    assert main(["--lang", "en", "--load-check", "docker", *extra, str(path)]) == 2


def test_cli_reports_a_check_that_cannot_run(tmp_path, monkeypatch, capsys):
    path = _write(tmp_path, "x.sql", "SELECT 1;\n")

    def missing(cmd, *, env=None, timeout=None):
        raise FileNotFoundError(cmd[0])

    monkeypatch.setattr(load_check, "_run", missing)
    assert main(["--lang", "en", "--load-check", "docker", str(path)]) == 2
    assert "docker not found" in capsys.readouterr().err


def test_explain_and_tui_refuse_load_check(capsys):
    assert main(["--lang", "en", "--explain", "GAP-001", "--load-check", "docker"]) == 2
    assert main(["--lang", "en", "--tui", "--load-check", "docker"]) == 2


# --- the real thing ---------------------------------------------------------


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_real_postgres_tells_the_broken_example_from_the_fixed_one():
    """The end-to-end example's two versions of the same ora2pg output:
    the generated one must fail on the gap its research doc names, the
    hand-fixed one must load cleanly."""
    broken = run_load_check([EXAMPLE / "generated" / "bulk_test_pkg.sql"], parse_target("docker"))
    assert [(e.category, e.gap_number, e.line) for e in broken.errors] == [("gap", "003", 21)]
    fixed = run_load_check([EXAMPLE / "generated_fixed" / "bulk_test_pkg.sql"], parse_target("docker"))
    assert fixed.errors == () and not fixed.failed
    assert fixed.server_version and fixed.server_version.startswith("16")


def test_data_files_load_after_tables_and_before_indexes(tmp_path):
    root = tmp_path / "out"
    root.mkdir()
    for name in ("INDEXES_output.sql", "COPY_output.sql", "TABLE_output.sql"):
        (root / name).write_text("SELECT 1;\n", encoding="utf-8")
    ordered, _ = order_files([root])
    assert [p.name for p in ordered] == ["TABLE_output.sql", "COPY_output.sql", "INDEXES_output.sql"]


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_real_postgres_loads_copy_data_and_keeps_reading_after_it(tmp_path):
    data = tmp_path / "data.sql"
    data.write_text(
        "CREATE TABLE t (id int, name text);\n"
        "COPY t (id, name) FROM STDIN;\n1\tone; two\n2\tO'Brien\n\\.\n"
        "DO $$ BEGIN ASSERT (SELECT name FROM t WHERE id = 2) = 'O''Brien'; END $$;\n"
        "SELECT * FROM missing_after_copy;\n",
        encoding="utf-8",
    )
    result = run_load_check([data], parse_target("docker"))
    assert [(e.line, e.sqlstate) for e in result.errors] == [(7, "42P01")]


def test_a_percent_type_on_a_missing_table_is_a_dependency(tmp_path, monkeypatch):
    path = _write(
        tmp_path,
        "trg.sql",
        "CREATE FUNCTION f() RETURNS int AS $body$\nDECLARE\n  x employees.salary%TYPE;\nBEGIN\n  RETURN 1;\nEND;\n$body$ LANGUAGE plpgsql;\n",
    )
    err = (
        'psql:{script}:8: ERROR:  42601: syntax error at or near "%"\n'
        "LINE 3:   x employees.salary%TYPE;\n"
        'CONTEXT:  invalid type name "employees.salary%TYPE"'
    )
    monkeypatch.setattr(load_check, "_run", FakePsql({"trg.sql": err}))
    (error,) = run_load_check([path], parse_target("dbname=x")).errors
    assert error.category == "dependency"


def test_a_flagged_construct_elsewhere_in_a_routine_does_not_claim_its_errors(tmp_path, monkeypatch):
    # Found on real ora2pg output for OraOpenSource Logger: a $IF further
    # down a procedure used to be blamed for a missing table on its header.
    body = (
        "CREATE FUNCTION f() RETURNS int AS $body$\n"
        "BEGIN\n"
        "  SELECT count(*) FROM logger_logs;\n"
        "  $IF dbms_db_version.ver_le_10 $THEN NULL; $END\n"
        "  RETURN 1;\n"
        "END;\n"
        "$body$ LANGUAGE plpgsql;\n"
    )
    path = _write(tmp_path, "f.sql", body)
    err = (
        'psql:{script}:8: ERROR:  42P01: relation "logger_logs" does not exist\n'
        "LINE 3:   SELECT count(*) FROM logger_logs;"
    )
    monkeypatch.setattr(load_check, "_run", FakePsql({"f.sql": err}))
    (error,) = run_load_check([path], parse_target("dbname=x")).errors
    assert (error.line, error.category, error.gap_number) == (4, "dependency", None)


# --- footprints of not_verifiable gaps in ora2pg's output -------------------


def _one_error(tmp_path, monkeypatch, body, line, message):
    path = _write(tmp_path, "gen.sql", body)
    err = f'psql:{{script}}:{line}: ERROR:  42601: {message}'
    monkeypatch.setattr(load_check, "_run", FakePsql({"gen.sql": err}))
    (error,) = run_load_check([path], parse_target("dbname=x")).errors
    return error.category, error.gap_number


def test_footprint_of_a_ref_cursor_type(tmp_path, monkeypatch):
    body = "CREATE OR REPLACE TYPE emp_api.emp_cur AS REFCURSOR;\n"
    assert _one_error(tmp_path, monkeypatch, body, 2, 'syntax error at or near "TYPE"') == ("gap", "115")


def test_footprint_of_a_spliced_constant(tmp_path, monkeypatch):
    body = (
        "CREATE FUNCTION f() RETURNS varchar AS $body$\nBEGIN\n"
        "    RETURN current_setting('fmt_pkg.c_stamp')::varchar(30)current_setting('fmt_pkg.c_date')::varchar(30)||;\n"
        "END;\n$body$ LANGUAGE plpgsql;\n"
    )
    err_line = "LINE 3:     RETURN current_setting"
    path = _write(tmp_path, "gen.sql", body)
    monkeypatch.setattr(
        load_check,
        "_run",
        FakePsql({"gen.sql": f'psql:{{script}}:6: ERROR:  42601: syntax error at or near "("\n{err_line}'}),
    )
    (error,) = run_load_check([path], parse_target("dbname=x")).errors
    assert (error.category, error.gap_number) == ("gap", "114")


def test_an_ordinary_cast_is_not_a_spliced_constant(tmp_path, monkeypatch):
    # Found on Logger: 'current_setting(...)::varchar(2);' used to match.
    body = (
        "CREATE FUNCTION f() RETURNS text AS $body$\nBEGIN\n"
        "    l_x := l_x || current_setting('logger.gc_cflf')::varchar(2);\n"
        "END;\n$body$ LANGUAGE plpgsql;\n"
    )
    path = _write(tmp_path, "gen.sql", body)
    err = 'psql:{script}:6: ERROR:  42601: "l_x" is not a known variable\nLINE 3:     l_x := l_x'
    monkeypatch.setattr(load_check, "_run", FakePsql({"gen.sql": err}))
    (error,) = run_load_check([path], parse_target("dbname=x")).errors
    assert error.category == "unknown"


def test_footprints_of_bare_calls(tmp_path, monkeypatch):
    trigger = (
        "CREATE OR REPLACE FUNCTION trigger_fct_t() RETURNS trigger AS $BODY$\nBEGIN\n"
        "  audit_pkg.touch;\nRETURN NEW;\nEND\n$BODY$\n LANGUAGE 'plpgsql';\n"
    )
    path = _write(tmp_path, "trg.sql", trigger)
    monkeypatch.setattr(
        load_check,
        "_run",
        FakePsql({"trg.sql": 'psql:{script}:8: ERROR:  42601: syntax error at or near "audit_pkg"\nLINE 3:   audit_pkg.touch;'}),
    )
    (error,) = run_load_check([path], parse_target("dbname=x")).errors
    assert error.gap_number == "117"

    procedure = (
        "CREATE OR REPLACE PROCEDURE job_pkg.run_all () AS $body$\nBEGIN\n"
        "    CALL job_pkg.refresh();\n    job_pkg.refresh();\n  END;\n$body$\nLANGUAGE PLPGSQL\n;\n"
    )
    path2 = tmp_path / "proc"
    path2.mkdir()
    p = _write(path2, "proc.sql", procedure)
    monkeypatch.setattr(
        load_check,
        "_run",
        FakePsql({"proc.sql": 'psql:{script}:9: ERROR:  42601: syntax error at or near "job_pkg"\nLINE 4:     job_pkg.refresh();'}),
    )
    (error,) = run_load_check([p], parse_target("dbname=x")).errors
    assert error.gap_number == "116"

    # A bare call with arguments inside a package is not GAP-116 (Logger's htp.p).
    other = procedure.replace("    job_pkg.refresh();\n", "    htp.p('<br />');\n")
    path3 = tmp_path / "other"
    path3.mkdir()
    q = _write(path3, "proc.sql", other)
    monkeypatch.setattr(
        load_check,
        "_run",
        FakePsql({"proc.sql": "psql:{script}:9: ERROR:  42601: syntax error at or near \"htp\"\nLINE 4:     htp.p('<br />');"}),
    )
    (error,) = run_load_check([q], parse_target("dbname=x")).errors
    assert error.category == "unknown"
