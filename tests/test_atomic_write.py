"""write_text_atomic() -- the guarantee every file this tool writes now
depends on: a reader sees the old contents or the new ones, never a
truncated file. Most important for `--fix --write`, which rewrites the
user's own SQL."""

import os
from pathlib import Path

import pytest

from ora2pg_gap_report.atomic_write import write_text_atomic


def test_it_writes_the_file(tmp_path):
    target = tmp_path / "out.txt"
    write_text_atomic(target, "hello\n")
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_it_creates_missing_parent_directories(tmp_path):
    # `--save reports/baseline.json` into a directory that doesn't exist
    # used to fail with a bare [Errno 2].
    target = tmp_path / "reports" / "nested" / "baseline.json"
    write_text_atomic(target, "{}\n")
    assert target.read_text(encoding="utf-8") == "{}\n"


def test_it_overwrites_an_existing_file(tmp_path):
    target = tmp_path / "out.txt"
    target.write_text("old content that is longer\n", encoding="utf-8")
    write_text_atomic(target, "new\n")
    assert target.read_text(encoding="utf-8") == "new\n"


def test_a_failed_write_leaves_the_previous_file_untouched(tmp_path, monkeypatch):
    # The whole point: a crash partway through must not destroy what was
    # already there.
    target = tmp_path / "out.txt"
    target.write_text("the original\n", encoding="utf-8")

    def exploding_replace(src, dst):
        raise OSError("simulated: disk full")

    monkeypatch.setattr(os, "replace", exploding_replace)
    with pytest.raises(OSError):
        write_text_atomic(target, "the replacement\n")

    assert target.read_text(encoding="utf-8") == "the original\n"


def test_a_failed_write_leaves_no_temp_file_behind(tmp_path, monkeypatch):
    target = tmp_path / "out.txt"
    target.write_text("the original\n", encoding="utf-8")

    def exploding_replace(src, dst):
        raise OSError("simulated: disk full")

    monkeypatch.setattr(os, "replace", exploding_replace)
    with pytest.raises(OSError):
        write_text_atomic(target, "x\n")

    assert [p.name for p in tmp_path.iterdir()] == ["out.txt"]


def test_the_temp_file_is_written_next_to_the_target(tmp_path, monkeypatch):
    # A rename is only atomic within one filesystem, so the temp file has
    # to live in the destination's directory, not the system temp dir.
    seen: list[Path] = []
    real_replace = os.replace

    def recording_replace(src, dst):
        seen.append(Path(src))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", recording_replace)
    target = tmp_path / "sub" / "out.txt"
    write_text_atomic(target, "x\n")

    assert seen[0].parent == target.parent


def test_a_write_error_surfaces_as_oserror_not_something_exotic(tmp_path):
    # Callers catch OSError specifically (cli.py's --output/--save/--fix
    # handlers all do), so the exception type is part of the contract.
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    with pytest.raises(OSError):
        write_text_atomic(blocker / "out.txt", "x\n")


def test_non_ascii_content_round_trips_as_utf8(tmp_path):
    target = tmp_path / "out.txt"
    write_text_atomic(target, "поле «id» — GAP-090\n")
    assert target.read_text(encoding="utf-8") == "поле «id» — GAP-090\n"
