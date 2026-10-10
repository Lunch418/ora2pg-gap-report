"""--pg-version: what a newer PostgreSQL no longer has a problem with, on
ora2pg 25.0's real output (tests/fixtures/pg_version/) and, under the
docker marker, PostgreSQL 16 and 17."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.cli import _load_target, main
from ora2pg_gap_report.detectors.json_table import find_json_table_calls
from ora2pg_gap_report.gap_registry import applies_on

FIXTURES = Path(__file__).parent / "fixtures" / "pg_version"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_json_table_tells_oracles_on_error_placement_apart():
    found = find_json_table_calls(_read("json_table_variants_source.sql"))
    assert [(f.object_name, f.message_id) for f in found] == [
        ("GX_JT_NESTED", "json_table"),
        ("GX_JT_ONERROR", "json_table.on_error"),
    ]


def test_what_applies_on_which_version():
    assert applies_on("json_table", 16) and not applies_on("json_table", 17) and not applies_on("json_table", 18)
    assert applies_on("json_table.on_error", 18)
    assert applies_on("autonomous_tx", 18)  # nothing recorded: still a gap


def test_docker_means_the_versions_image():
    assert _load_target("docker", 17) == "docker:postgres:17-alpine"
    assert _load_target("docker", None) == "docker"
    assert _load_target("docker:my/pg:1", 17) == "docker:my/pg:1"
    assert _load_target("host=db dbname=x", 17) == "host=db dbname=x"


def _scan(tmp_path, capsys, *flags):
    out = tmp_path / "r.json"
    assert main(["--lang", "en", "-f", "json", "-o", str(out), *flags, str(FIXTURES / "json_table_variants_source.sql")]) == 0
    findings = json.loads(out.read_text(encoding="utf-8"))["findings"]
    # The fixture's NUMBER columns are GAP-130's, not this test's.
    return [f["message_id"] for f in findings if f["detector"] == "json_table"], capsys.readouterr().err


def test_cli_leaves_out_what_the_target_no_longer_has_and_says_so(tmp_path, capsys):
    assert _scan(tmp_path, capsys)[0] == ["json_table", "json_table.on_error"]
    ids, err = _scan(tmp_path, capsys, "--pg-version", "17")
    assert ids == ["json_table.on_error"]
    assert "PostgreSQL 17: 1 finding not shown - no longer a problem there (GAP-017)" in " ".join(err.split())


def test_cli_warns_about_a_version_older_than_the_confirmed_one(tmp_path, capsys):
    ids, err = _scan(tmp_path, capsys, "--pg-version", "14")
    assert ids == ["json_table", "json_table.on_error"]
    assert "confirmed on PostgreSQL 16" in " ".join(err.split())


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_on_postgresql_16_and_17(tmp_path):
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    simple = tmp_path / "simple.sql"
    simple.write_text(
        _read("json_table_PROCEDURE_output.sql")
        + "DO $$ DECLARE n bigint; BEGIN CALL gx_jt(n); ASSERT n = 2; END $$;\n",
        encoding="utf-8",
    )
    variants = tmp_path / "variants.sql"
    variants.write_text(_read("json_table_variants_PROCEDURE_output.sql"), encoding="utf-8")

    def load(path, version):
        return run_load_check([path], parse_target(f"docker:postgres:{version}-alpine")).errors

    assert [e.message for e in load(simple, 16)][0] == 'syntax error at or near "COLUMNS"'
    assert load(simple, 17) == ()  # loads and returns the same count
    # NESTED PATH loads on 17; Oracle's ERROR ON ERROR before COLUMNS does not
    assert [e.message for e in load(variants, 17)] == ['syntax error at or near "ERROR"']
