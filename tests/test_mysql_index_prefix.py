"""GAP-127: an index on a column prefix, on real ora2pg 25.0 output
(tests/fixtures/mysql_indexes/) and, under the docker marker, PostgreSQL 16."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from ora2pg_gap_report.detectors.mysql_index_prefix import find_mysql_index_prefix
from ora2pg_gap_report.prepare import prepare_mysql_indexes

FIXTURES = Path(__file__).parent / "fixtures" / "mysql_indexes"


def _read(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_prefix_indexes_are_flagged_in_every_spelling():
    source = (
        "CREATE TABLE `t` (\n  `a` text,\n  `b` varchar(200),\n"
        "  KEY `k` (`a`(20)),\n  INDEX `i` (`b`(10), `a`(5)),\n  UNIQUE KEY `u` (`b`(8)),\n  KEY `plain` (`b`)\n);\n"
    )
    assert [(f.line, f.snippet) for f in find_mysql_index_prefix(source)] == [
        (4, "k (a(20))"),
        (5, "i (b(10), a(5))"),
        (6, "u (b(8))"),
    ]


def test_a_length_in_a_column_type_or_a_string_is_not_a_prefix():
    source = "CREATE TABLE `t` (`a` varchar(20), `b` decimal(10,2) DEFAULT '0', KEY `k` (`a`), c char(3) DEFAULT 'KEY x (y(2))');\n"
    assert find_mysql_index_prefix(source) == []


def test_ora2pg_output_shapes():
    # the INDEX spelling: an unterminated quoted identifier
    assert 'CREATE INDEX idx_note ON t1 (note"(20);' in _read("prefix_index_TABLE_output.sql")
    # UNIQUE: a column name that does not exist
    assert 'ALTER TABLE t1 ADD UNIQUE ("note(20");' in _read("prefix_unique_TABLE_output.sql")


def test_prepare_leaves_a_prefix_index_for_a_person_to_decide():
    source = _read("prefix_index_source.sql")
    assert prepare_mysql_indexes(source) == (source, 0)


def _docker_usable():
    if not sys.platform.startswith("linux") or shutil.which("docker") is None:
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@pytest.mark.docker
@pytest.mark.skipif(not _docker_usable(), reason="needs a working docker (Linux)")
def test_on_postgresql(tmp_path):
    from ora2pg_gap_report.load_check import parse_target, run_load_check

    index = tmp_path / "index.sql"
    index.write_text(_read("prefix_index_TABLE_output.sql"), encoding="utf-8")
    unique = tmp_path / "unique.sql"
    unique.write_text(_read("prefix_unique_TABLE_output.sql"), encoding="utf-8")
    # the open quote swallows the rest of the file: --load-check skips it
    # instead of reporting it loaded
    result = run_load_check([index], parse_target("docker"), dialect="mysql")
    assert [s.reason for s in result.skipped_files] == ["unterminated"] and result.incomplete
    errors = run_load_check([unique], parse_target("docker"), dialect="mysql").errors
    assert [(e.message, e.gap_number) for e in errors] == [('column "note(20" named in key does not exist', "127")]
