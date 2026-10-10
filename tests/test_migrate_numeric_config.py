"""--migrate converts with a copy of ora2pg's own ora2pg.conf that keeps
NUMBER decimal (GAP-130, GAP-131): reading that file, the settings put
into it, and -- under the docker marker -- the real ora2pg 25.0 output
with and without it."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report import migrate, ora2pg_wrapper
from ora2pg_gap_report.migrate import CONFIG_NAME, handled_by_migrate, run_migration
from ora2pg_gap_report.ora2pg_wrapper import default_config, numeric_config

FIXTURES = Path(__file__).parent / "fixtures" / "silent_numbers"

SHIPPED = """# ora2pg.conf as shipped (excerpt)
PG_NUMERIC_TYPE	1
PG_INTEGER_TYPE	1
DEFAULT_NUMERIC bigint
#DATA_TYPE	VARCHAR2:varchar,FLOAT:double precision
NULL_EQUAL_EMPTY	0
"""


def _settings(text):
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def test_the_three_settings_replace_the_shipped_ones():
    assert _settings(numeric_config(SHIPPED)) == [
        "PG_NUMERIC_TYPE\t0",
        "PG_INTEGER_TYPE\t1",
        "DEFAULT_NUMERIC\tnumeric",
        "NULL_EQUAL_EMPTY\t0",
        "DATA_TYPE\tFLOAT:numeric",
    ]


def test_an_existing_data_type_line_keeps_its_mappings():
    text = "DATA_TYPE\tVARCHAR2:varchar,FLOAT:double precision,DATE:timestamp\n"
    assert "DATA_TYPE\tVARCHAR2:varchar,FLOAT:numeric,DATE:timestamp" in numeric_config(text)
    text = "DATA_TYPE\tVARCHAR2:varchar\n"
    assert "DATA_TYPE\tVARCHAR2:varchar,FLOAT:numeric" in numeric_config(text)


def test_missing_settings_are_added():
    assert _settings(numeric_config("ORACLE_DSN\tdbi:Oracle:x\n")) == [
        "ORACLE_DSN\tdbi:Oracle:x",
        "PG_NUMERIC_TYPE\t0",
        "DEFAULT_NUMERIC\tnumeric",
        "DATA_TYPE\tFLOAT:numeric",
    ]


def test_default_config_reads_the_file_named_by_help(tmp_path):
    conf = tmp_path / "ora2pg.conf"
    conf.write_text(SHIPPED, encoding="utf-8")
    fake = tmp_path / "ora2pg"
    fake.write_text(
        f"#!/bin/sh\necho '    -c | --conf file  : Set an alternate configuration file other than the'\n"
        f"echo '                        default {conf}.'\n",
        encoding="utf-8",
    )
    fake.chmod(0o755)
    if sys.platform.startswith("win"):
        pytest.skip("a shell script stands in for ora2pg")
    assert default_config(str(fake)) == SHIPPED


def test_default_config_is_none_when_ora2pg_cannot_say(tmp_path):
    assert default_config(str(tmp_path / "no-such-ora2pg")) is None


def test_handled_notes_name_the_config():
    assert handled_by_migrate("oracle", numeric_config=True)["number_without_precision"] == "checklist_migrate_configured"
    assert "number_as_float" not in handled_by_migrate("oracle")


SOURCE = "CREATE TABLE gx_prices (id NUMBER, price NUMBER, qty NUMBER(5));\n"


@pytest.fixture
def converted(monkeypatch):
    """run_convert stubbed: which config each call got."""
    configs = []

    def fake(input_file, object_type, dialect="oracle", ora2pg_bin="ora2pg", lang="ru", config=None):
        configs.append(config)
        return ""

    monkeypatch.setattr(migrate, "run_convert", fake)
    monkeypatch.setattr(migrate, "default_config", lambda ora2pg_bin: SHIPPED)
    return configs


def test_migrate_writes_and_uses_the_config(tmp_path, converted):
    src = tmp_path / "s.sql"
    src.write_text(SOURCE, encoding="utf-8")
    result = run_migration([src], tmp_path / "out")
    conf = tmp_path / "out" / CONFIG_NAME
    assert result.numeric_config and conf.exists()
    assert "DEFAULT_NUMERIC\tnumeric" in conf.read_text(encoding="utf-8")
    assert set(converted) == {conf}
    assert "PG_NUMERIC_TYPE 0" in (tmp_path / "out" / "MIGRATION.md").read_text(encoding="utf-8")


def test_keep_ora2pg_types_opts_out_and_removes_an_old_config(tmp_path, converted):
    src = tmp_path / "s.sql"
    src.write_text(SOURCE, encoding="utf-8")
    run_migration([src], tmp_path / "out")
    converted.clear()
    result = run_migration([src], tmp_path / "out", numeric_types=False)
    assert not result.numeric_config
    assert not (tmp_path / "out" / CONFIG_NAME).exists()
    assert set(converted) == {None}


def test_other_dialects_are_left_alone(tmp_path, converted):
    src = tmp_path / "s.sql"
    src.write_text("CREATE TABLE t (id int);\n", encoding="utf-8")
    assert not run_migration([src], tmp_path / "out", dialect="mysql").numeric_config


# --- the real ora2pg 25.0 ----------------------------------------------------------


def _docker_image(image):
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_image("ora2pg:25.0"), reason="needs the ora2pg:25.0 docker image")
def test_real_ora2pg_keeps_number_decimal(tmp_path):
    shipped = default_config("docker:ora2pg:25.0")
    assert shipped is not None and "DEFAULT_NUMERIC" in shipped
    tables = FIXTURES / "oracle_tables.sql"
    functions = FIXTURES / "oracle_functions.sql"
    config = tmp_path / "ora2pg.conf"
    config.write_text(numeric_config(shipped), encoding="utf-8")
    run = ora2pg_wrapper.run_convert
    with_config = run(tables, "TABLE", ora2pg_bin="docker:ora2pg:25.0", config=config)
    assert "price numeric," in with_config and "amount decimal(10,2)," in with_config
    assert "qty integer" in with_config  # NUMBER(5) stays an integer
    body = run(functions, "FUNCTION", ora2pg_bin="docker:ora2pg:25.0", config=config)
    assert "v numeric := 2.5;" in body and "a decimal(10,2) := 0.1;" in body
    as_shipped = run(tables, "TABLE", ora2pg_bin="docker:ora2pg:25.0")
    assert "price bigint," in as_shipped and "amount double precision," in as_shipped
