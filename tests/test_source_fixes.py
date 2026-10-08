"""Repairs that need the source (source_fixes.py), on real ora2pg 25.0
output recorded in tests/fixtures/source_fixes/: what each one changes,
and -- under the docker marker -- that PostgreSQL 16 rejects or
misbehaves on the output before it and loads and behaves after it."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report import source_fixes as sf

FIXTURES = Path(__file__).parent / "fixtures" / "source_fixes"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


ORACLE = _read("oracle_source.sql")
MYSQL = _read("mysql_source.sql")


def test_constants_are_worked_out_from_literals_and_chains():
    constants = {(c.package, c.name): c.literal for c in sf.package_constants(ORACLE)}
    assert constants == {
        ("file_pkg", "g_os_windows"): "'w'",
        ("file_pkg", "g_mode"): "3",
        ("fmt_pkg", "c_date"): "'YYYY-MM-DD'",
        ("fmt_pkg", "c_stamp"): "'YYYY-MM-DD HH24:MI'",
    }  # g_counter is a variable: its value changes, so it is left alone


def test_a_constant_whose_value_cannot_be_worked_out_is_skipped():
    source = (
        "CREATE OR REPLACE PACKAGE p AS\n"
        "  c_now CONSTANT DATE := SYSDATE;\n"
        "  c_q CONSTANT VARCHAR2(9) := 'it''s';\n"
        "  c_x CONSTANT VARCHAR2(9) := other_pkg.c_y || 'z';\n"
        "END p;\n/\n"
    )
    assert [(c.name, c.literal) for c in sf.package_constants(source)] == [("c_q", "'it''s'")]


def test_constant_repairs_on_real_output():
    fixed, count = sf.restore_constants(_read("oracle_PACKAGE_output.sql"), sf.package_constants(ORACLE))
    assert "p_os text DEFAULT 'w')" in fixed                                  # GAP-119
    assert "RETURN 'YYYY-MM-DD HH24:MI';" in fixed                             # GAP-114
    assert "RETURN 'YYYY-MM-DD'::varchar(30);" in fixed                        # GAP-036's constant read
    assert "p_os = 'w'::varchar(1)" in fixed
    assert "current_setting" not in fixed
    assert count == 4  # a default, two reads, a spliced chain
    assert sf.restore_constants(fixed, sf.package_constants(ORACLE)) == (fixed, 0)


def test_get_ddl_spliced_shape():
    # ora2pg on DBMS_METADATA.GET_DDL's text leaves the second operand bare.
    line = "    RETURN current_setting('fmt_pkg.c_stamp')::varchar(30)c_date||;"
    assert sf.restore_constants(line, sf.package_constants(ORACLE)) == ("    RETURN 'YYYY-MM-DD HH24:MI';", 1)


LOGGER = """CREATE OR REPLACE PACKAGE logger AS
  gc_date_format CONSTANT VARCHAR2(255) := 'DD-MON-YYYY HH24:MI:SS';
  gc_timestamp_format CONSTANT VARCHAR2(255) := gc_date_format || ':FF';
  gc_timestamp_tz_format CONSTANT VARCHAR2(255) := gc_timestamp_format || ' TZR';
END logger;
/
"""


@pytest.mark.parametrize(
    "spliced",
    [
        # every shape ora2pg 25.0 wrote for OraOpenSource Logger's tochar()
        # over six runs on the same input
        "current_setting('logger.gc_timestamp_tz_format')::varchar(255)gc_timestamp_format||",
        "current_setting('logger.gc_timestamp_tz_format')::varchar(255)"
        "current_setting('logger.gc_timestamp_format')::varchar(255)"
        "current_setting('logger.gc_date_format')::varchar(255)||||",
    ],
)
def test_every_spliced_chain_shape(spliced):
    line = f"    return to_char(p_val, {spliced});"
    fixed, count = sf.restore_constants(line, sf.package_constants(LOGGER))
    assert (fixed, count) == ("    return to_char(p_val, 'DD-MON-YYYY HH24:MI:SS:FF TZR');", 1)


def test_a_default_is_only_replaced_for_its_own_package():
    head = "CREATE OR REPLACE FUNCTION other_pkg.f (p text DEFAULT g_os_windows) RETURNS text AS $body$"
    assert sf.restore_constants(head, sf.package_constants(ORACLE)) == (head, 0)


def test_statement_trigger_is_restored():
    fixed, count = sf.restore_statement_triggers(_read("oracle_TRIGGER_output.sql"), sf.statement_trigger_names(ORACLE))
    assert count == 1
    assert "FOR EACH STATEMENT" in fixed and "FOR EACH ROW" not in fixed
    assert "RETURN NULL;" in fixed and "RETURN NEW;" not in fixed


def test_row_triggers_are_left_alone():
    row = ORACLE.replace("AFTER INSERT ON gx_orders\n", "AFTER INSERT ON gx_orders FOR EACH ROW\n")
    output = _read("oracle_TRIGGER_output.sql")
    assert sf.restore_statement_triggers(output, sf.statement_trigger_names(row)) == (output, 0)


def test_enum_type_is_added_before_its_table():
    types = sf.mysql_enum_types(MYSQL)
    assert types == {"orders_status_t": "CREATE TYPE orders_status_t AS ENUM ('new', 'paid', 'shipped');"}
    fixed, count = sf.restore_enum_types(_read("mysql_TABLE_output.sql"), types)
    assert count == 1
    assert fixed.index("CREATE TYPE orders_status_t") < fixed.index("CREATE TABLE orders")
    assert sf.restore_enum_types(fixed, types) == (fixed, 0)


def test_enum_values_with_quotes():
    source = "CREATE TABLE t (`c` enum('it''s','b\\'c') NOT NULL);"
    assert sf.mysql_enum_types(source)["t_c_t"] == "CREATE TYPE t_c_t AS ENUM ('it''s', 'b''c');"


# --- PostgreSQL 16: before and after -----------------------------------------


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _load(tmp_path, *texts, dialect="oracle"):
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    files = []
    for i, text in enumerate(texts):
        path = tmp_path / f"{i}.sql"
        path.write_text(text, encoding="utf-8")
        files.append(path)
    return run_load_check(files, parse_target("docker"), dialect=dialect).errors


docker = pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")

CONSTANT_CHECKS = (
    "DO $$ BEGIN\n"
    "  ASSERT fmt_pkg.stamp_fmt() = 'YYYY-MM-DD HH24:MI';\n"
    "  ASSERT fmt_pkg.date_fmt() = 'YYYY-MM-DD';\n"
    "  ASSERT file_pkg.sep() = 'win' AND file_pkg.sep('u') = 'unix';\n"
    "END $$;\n"
)


@pytest.mark.docker
@docker
def test_constants_before_and_after(tmp_path):
    output = _read("oracle_PACKAGE_output.sql")
    (tmp_path / "before").mkdir()
    assert _load(tmp_path / "before", output, CONSTANT_CHECKS)
    fixed, _ = sf.restore_constants(output, sf.package_constants(ORACLE))
    (tmp_path / "after").mkdir()
    assert _load(tmp_path / "after", fixed, CONSTANT_CHECKS) == ()


TRIGGER_SETUP = "CREATE TABLE gx_orders (id int);\nCREATE TABLE gx_fired (n int);\nINSERT INTO gx_fired VALUES (0);\n"
TRIGGER_CHECK = (
    "INSERT INTO gx_orders SELECT generate_series(1, 5);\n"
    "DO $$ BEGIN ASSERT (SELECT n FROM gx_fired) = 1, 'fired once per row'; END $$;\n"
)


@pytest.mark.docker
@docker
def test_statement_trigger_before_and_after(tmp_path):
    output = _read("oracle_TRIGGER_output.sql")
    (tmp_path / "before").mkdir()
    before = _load(tmp_path / "before", TRIGGER_SETUP, output, TRIGGER_CHECK)
    assert [e.sqlstate for e in before] == ["P0004"]  # five times, not once
    fixed, _ = sf.restore_statement_triggers(output, sf.statement_trigger_names(ORACLE))
    (tmp_path / "after").mkdir()
    assert _load(tmp_path / "after", TRIGGER_SETUP, fixed, TRIGGER_CHECK) == ()


@pytest.mark.docker
@docker
def test_enum_before_and_after(tmp_path):
    output = _read("mysql_TABLE_output.sql")
    check = (
        "INSERT INTO orders VALUES (1, 'shipped'), (2, 'new');\n"
        "DO $$ BEGIN ASSERT (SELECT array_agg(status::text ORDER BY status) FROM orders) = ARRAY['new', 'shipped']; END $$;\n"
    )
    (tmp_path / "before").mkdir()
    assert _load(tmp_path / "before", output, check, dialect="mysql")
    fixed, _ = sf.restore_enum_types(output, sf.mysql_enum_types(MYSQL))
    (tmp_path / "after").mkdir()
    assert _load(tmp_path / "after", fixed, check, dialect="mysql") == ()
