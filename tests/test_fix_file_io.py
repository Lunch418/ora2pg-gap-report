"""--fix --write rewrites a user's file in place, so everything about the
file that the fix is not about has to come back exactly as it was. It
did not: the file was read as UTF-8 with errors="replace" and written back
as UTF-8, so a cp1251 file -- what ora2pg writes for a Russian-locale
source with CLIENT_ENCODING/NLS_LANG set that way -- had every Cyrillic
letter turned into U+FFFD for good; Windows line endings were translated
to '\\n' on every line, not just the fixed one; and the temporary file the
write goes through made the result 0600 whatever the original was.

Now the bytes are decoded with surrogateescape (anything that is not UTF-8
survives as-is -- the fixers only ever touch ASCII), line endings are not
translated, and the original file's permissions are kept."""

import os
import stat
import sys

import pytest

from ora2pg_gap_report.cli import main

BUGGY = "CREATE TABLE t (id bigint GENERATED ALWAYS AS IDENTITY ((START WITH 1)));\n"
FIXED = "CREATE TABLE t (id bigint GENERATED ALWAYS AS IDENTITY (START WITH 1));\n"
COMMENT = "-- Таблица клиентов\n"


def test_a_cp1251_file_keeps_every_byte_the_fix_is_not_about(tmp_path, capsys):
    path = tmp_path / "out.sql"
    path.write_bytes((COMMENT + BUGGY).encode("cp1251"))

    assert main(["--fix", "--write", str(path)]) == 0
    assert path.read_bytes() == (COMMENT + FIXED).encode("cp1251")


def test_windows_line_endings_survive_a_fix(tmp_path, capsys):
    path = tmp_path / "out.sql"
    path.write_bytes((COMMENT + BUGGY).replace("\n", "\r\n").encode("utf-8"))

    assert main(["--fix", "--write", str(path)]) == 0
    assert path.read_bytes() == (COMMENT + FIXED).replace("\n", "\r\n").encode("utf-8")


def test_a_utf8_bom_survives_a_fix(tmp_path, capsys):
    path = tmp_path / "out.sql"
    path.write_bytes(b"\xef\xbb\xbf" + (COMMENT + BUGGY).encode("utf-8"))

    assert main(["--fix", "--write", str(path)]) == 0
    assert path.read_bytes() == b"\xef\xbb\xbf" + (COMMENT + FIXED).encode("utf-8")


def test_the_dry_run_diff_of_a_cp1251_file_is_a_patch_in_the_files_own_bytes(tmp_path, capsysbinary):
    # Printing the diff used to go through the console's text encoding,
    # which cannot represent bytes that were never UTF-8 in the first
    # place. The diff is now written as the file's own bytes -- which is
    # also what `patch`/`git apply` need to apply it to that file.
    path = tmp_path / "out.sql"
    path.write_bytes((COMMENT + BUGGY).encode("cp1251"))

    assert main(["--fix", str(path)]) == 0
    out = capsysbinary.readouterr().out
    assert COMMENT.encode("cp1251") in out
    assert b"+" + FIXED.encode("ascii") in out
    assert path.read_bytes() == (COMMENT + BUGGY).encode("cp1251")


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_fixed_file_keeps_its_permissions(tmp_path, capsys):
    path = tmp_path / "out.sql"
    path.write_text(BUGGY, encoding="utf-8")
    path.chmod(0o644)

    assert main(["--fix", "--write", str(path)]) == 0
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o644
