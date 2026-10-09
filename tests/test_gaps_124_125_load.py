"""GAP-124/125 on PostgreSQL 16: ora2pg 25.0's real output for a GET_DDL
export and an SSMS script (tests/fixtures/gaps_124_125/) does not load on
a fresh database; --load-check ties the errors to the gaps; done the way
each research doc says, it loads."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.autofix import fix_mssql_missing_schema
from ora2pg_gap_report.load_check import parse_target, run_load_check

FIXTURES = Path(__file__).parent / "fixtures" / "gaps_124_125"


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


pytestmark = [pytest.mark.docker, pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")]

ORACLE = ["oracle_TABLE_output.sql", "oracle_SEQUENCE_output.sql", "oracle_VIEW_output.sql", "oracle_PACKAGE_output.sql", "oracle_TRIGGER_output.sql"]
MSSQL = ["mssql_TABLE_output.sql", "mssql_VIEW_output.sql", "mssql_FUNCTION_output.sql"]


def _load(tmp_path, texts, dialect):
    files = []
    for i, text in enumerate(texts):
        path = tmp_path / f"{i}.sql"
        path.write_text(text, encoding="utf-8")
        files.append(path)
    return run_load_check(files, parse_target("docker"), dialect=dialect).errors


def _read(names):
    return [(FIXTURES / n).read_text(encoding="utf-8") for n in names]


def test_oracle_as_ora2pg_writes_it_and_with_schema_and_search_path(tmp_path):
    (tmp_path / "a").mkdir()
    errors = _load(tmp_path / "a", _read(ORACLE), "oracle")
    def head(e, names):
        return _read([names[int(Path(e.file).stem)]])[0].splitlines()[e.statement_line - 1]

    creates = [e for e in errors if head(e, ORACLE).startswith(("CREATE TABLE", "CREATE SEQUENCE", "CREATE OR REPLACE VIEW"))]
    # the table and the sequence fail for the missing schema
    assert [(e.sqlstate, e.gap_number) for e in creates if e.sqlstate == "3F000"] == [("3F000", "124")] * 2
    # the rest echo the failed CREATE TABLE (its ALTER TABLE, the view and
    # the trigger that name its table)
    assert all(e.category == "dependency" for e in errors if e not in creates)
    # creating the schema alone leaves the trigger and the view body, which lost it
    (tmp_path / "b").mkdir()
    errors = _load(tmp_path / "b", ["CREATE SCHEMA hr;\n", *_read(ORACLE)], "oracle")
    assert {e.message for e in errors} == {'relation "gx_emp" does not exist'}
    (tmp_path / "c").mkdir()
    check = "INSERT INTO hr.gx_emp VALUES (1);\nDO $$ BEGIN ASSERT (SELECT count(*) FROM hr.gx_v) = 1; END $$;\n"
    texts = ["CREATE SCHEMA hr;\nSET search_path = hr, public;\n", *_read(ORACLE), check]
    assert _load(tmp_path / "c", texts, "oracle") == ()


def test_mssql_as_ora2pg_writes_it_and_after_fix(tmp_path):
    (tmp_path / "a").mkdir()
    errors = _load(tmp_path / "a", _read(MSSQL), "mssql")
    creates = [e for e in errors if _read([MSSQL[int(Path(e.file).stem)]])[0].splitlines()[e.statement_line - 1].startswith("CREATE")]
    schema = [e for e in creates if e.sqlstate == "3F000"]
    assert len(schema) == 2 and all((e.category, e.gap_number) == ("fixable", "125") for e in schema)
    (tmp_path / "b").mkdir()
    fixed = [fix_mssql_missing_schema(t)[0] for t in _read(MSSQL)]
    assert not [e for e in _load(tmp_path / "b", fixed, "mssql") if e.sqlstate in ("3F000", "42P01")]
