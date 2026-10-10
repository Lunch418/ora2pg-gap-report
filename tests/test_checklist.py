import datetime
import io
import os
from pathlib import Path

import pytest

from ora2pg_gap_report.checklist import (
    MARKER,
    ChecklistError,
    ItemKey,
    build_items,
    read_previous,
    write_checklist,
)
from ora2pg_gap_report.cli import main
from ora2pg_gap_report.models import Finding

TODAY = datetime.date(2026, 10, 5)


def _finding(detector="bulk_collect", obj="PKG.PROC", line=10, source="pkg.sql"):
    return Finding(
        detector=detector,
        severity="high",
        object_name=obj,
        line=line,
        snippet="x",
        message_id=detector,
        source_file=source,
    )


def _render(findings, previous=None, scanned=("pkg.sql",), lang="en"):
    out = io.StringIO()
    write_checklist(findings, out, lang=lang, previous=previous, scanned_files=scanned, version="9.9", today=TODAY)
    return out.getvalue()


@pytest.fixture(autouse=True)
def _in_tmp(tmp_path, monkeypatch):
    # Item keys hold paths relative to the working directory.
    monkeypatch.chdir(tmp_path)


def test_first_checklist_lists_every_object_once_per_gap_with_its_lines():
    text = _render([_finding(line=10), _finding(line=12), _finding(obj="PKG.OTHER", line=40)])
    assert text.startswith(MARKER)
    assert "**Done: 0 of 2 (0 %)**" in text
    assert "## GAP-003 " in text
    assert "- [ ] `PKG.PROC` - `pkg.sql` (lines 10, 12) <!-- item: bulk_collect | PKG.PROC | pkg.sql -->" in text
    assert "(line 40)" in text
    assert "collections-and-bulk.md" in text          # the recipe link
    assert "`ora2pg-gap-report --explain GAP-003`" in text
    assert "updated 2026-10-05" in text


def test_ticks_survive_regeneration_and_gone_items_tick_themselves():
    first = _render([_finding(obj="A"), _finding(obj="B"), _finding(obj="C")])
    edited = first.replace("- [ ] `A`", "- [x] `A`")
    previous = read_previous_from_text(edited)
    # B was fixed in the source; A is still there but someone ticked it
    second = _render([_finding(obj="A"), _finding(obj="C")], previous=previous)
    assert "- [x] `A`" in second
    assert "- [x] `B` - `pkg.sql` - no longer found" in second
    assert "- [ ] `C`" in second
    assert "**Done: 2 of 3 (67 %)**" in second


def test_items_in_files_not_scanned_this_time_keep_their_state():
    first = _render([_finding(obj="A", source="a.sql"), _finding(obj="B", source="b.sql")], scanned=("a.sql", "b.sql"))
    previous = read_previous_from_text(first)
    # only a.sql scanned now: B must not be reported as fixed
    second = _render([_finding(obj="A", source="a.sql")], previous=previous, scanned=("a.sql",))
    assert "- [ ] `B` - `b.sql` - file not scanned this time" in second
    assert "**Done: 0 of 2 (0 %)**" in second


def test_a_gap_whose_items_are_all_done_says_so_and_drops_its_advice():
    first = _render([_finding(obj="A")])
    second = _render([], previous=read_previous_from_text(first))
    assert "## GAP-003 " in second and " - done" in second
    assert "What to do" not in second
    assert "**Done: 1 of 1 (100 %)**" in second


def test_nothing_found_and_nothing_remembered():
    text = _render([])
    assert "nothing to tick off" in text


def test_keys_survive_separators_and_comment_ends_in_names():
    key = ItemKey("bulk_collect", 'odd | name --> "x"', "dir/f.sql")
    assert ItemKey.decode(key.encode()) == key
    assert "-->" not in key.encode()


def test_build_items_sorts_open_items_first():
    previous = {ItemKey("bulk_collect", "A", "pkg.sql"): True}
    items = build_items([_finding(obj="A"), _finding(obj="Z")], previous, ["pkg.sql"])
    assert [i.key.object_name for i in items["bulk_collect"]] == ["Z", "A"]


def test_a_file_that_is_not_a_checklist_is_refused(tmp_path):
    notes = tmp_path / "NOTES.md"
    notes.write_text("# my notes\n", encoding="utf-8")
    with pytest.raises(ChecklistError):
        read_previous(notes)
    assert read_previous(tmp_path / "missing.md") is None


def read_previous_from_text(text):
    path = Path("prev.md")
    path.write_text(text, encoding="utf-8")
    return read_previous(path)


# --- through the CLI ---------------------------------------------------------

SOURCE = """CREATE OR REPLACE PACKAGE BODY pkg AS
  PROCEDURE p IS
    TYPE t IS TABLE OF NUMBER;
    v t;
  BEGIN
    SELECT 1 BULK COLLECT INTO v FROM dual;
  END;
END pkg;
/
"""


def test_cli_checklist_round_trip(capsys):
    Path("pkg.sql").write_text(SOURCE, encoding="utf-8")
    assert main(["--lang", "en", "pkg.sql", "-f", "checklist", "-o", "MIGRATION.md"]) == 0
    text = Path("MIGRATION.md").read_text(encoding="utf-8")
    assert "**Done: 0 of 1 (0 %)**" in text

    Path("pkg.sql").write_text("CREATE TABLE t (id NUMBER);\n", encoding="utf-8")
    assert main(["--lang", "en", "pkg.sql", "-f", "checklist", "-o", "MIGRATION.md"]) == 0
    text = Path("MIGRATION.md").read_text(encoding="utf-8")
    assert "**Done: 1 of 1 (100 %)**" in text
    assert "no longer found" in text


def test_cli_refuses_to_overwrite_a_foreign_file(capsys):
    Path("pkg.sql").write_text(SOURCE, encoding="utf-8")
    Path("NOTES.md").write_text("# mine\n", encoding="utf-8")
    assert main(["--lang", "en", "pkg.sql", "-f", "checklist", "-o", "NOTES.md"]) == 2
    assert Path("NOTES.md").read_text(encoding="utf-8") == "# mine\n"
    assert "not overwriting" in capsys.readouterr().err


def test_cli_checklist_to_stdout(capsys):
    Path("pkg.sql").write_text(SOURCE, encoding="utf-8")
    assert main(["--lang", "ru", "pkg.sql", "-f", "checklist"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(MARKER)
    assert "Сделано: 0 из 1" in out
    assert os.listdir(".") == ["pkg.sql"]


# --- ticks that follow a renamed file or a moved routine ----------------------


def _ticked_checklist(tmp_path, findings, scanned):
    from ora2pg_gap_report.checklist import read_previous, write_checklist

    out = tmp_path / "MIGRATION.md"
    buffer = io.StringIO()
    write_checklist(findings, buffer, lang="en", scanned_files=scanned)
    out.write_text(buffer.getvalue().replace("- [ ]", "- [x]"), encoding="utf-8")
    return read_previous(out)


def _render_after(findings, previous, scanned):
    from ora2pg_gap_report.checklist import write_checklist

    buffer = io.StringIO()
    write_checklist(findings, buffer, lang="en", previous=previous, scanned_files=scanned)
    return buffer.getvalue()


def _found_in(detector, obj, file, line=1):
    from ora2pg_gap_report.models import Finding

    return Finding(detector=detector, severity="high", object_name=obj, line=line, snippet="x",
                   message_id=detector, source_file=file)


def test_a_tick_follows_its_object_into_a_renamed_file(tmp_path):
    previous = _ticked_checklist(tmp_path, [_found_in("autonomous_tx", "PKG.LOG", "old/pkg.pkb")], ["old/pkg.pkb"])
    text = _render_after([_found_in("autonomous_tx", "PKG.LOG", "new/pkg_body.sql")], previous, ["new/pkg_body.sql"])
    assert "- [x] `PKG.LOG` - `new/pkg_body.sql`" in text
    assert "was: `old/pkg.pkb`" in text
    assert text.count("PKG.LOG") == 2  # the item and its key comment, not a second item for the old file
    assert "Done: 1 of 1" in text


def test_a_tick_follows_a_routine_into_another_package(tmp_path):
    previous = _ticked_checklist(tmp_path, [_found_in("autonomous_tx", "PKG.LOG", "a.pkb")], ["a.pkb"])
    text = _render_after([_found_in("autonomous_tx", "PKG_LOGGING.LOG", "a.pkb")], previous, ["a.pkb"])
    assert "- [x] `PKG_LOGGING.LOG`" in text and "was: `PKG.LOG`" in text


def test_an_ambiguous_move_carries_nothing(tmp_path):
    # Two old candidates for one new item: no guessing.
    previous = _ticked_checklist(
        tmp_path, [_found_in("autonomous_tx", "A.LOG", "a.pkb"), _found_in("autonomous_tx", "B.LOG", "a.pkb")], ["a.pkb"]
    )
    text = _render_after([_found_in("autonomous_tx", "C.LOG", "a.pkb")], previous, ["a.pkb"])
    assert "- [ ] `C.LOG`" in text and "was:" not in text


def test_a_bare_name_is_not_moved_by_its_last_part(tmp_path):
    previous = _ticked_checklist(tmp_path, [_found_in("authid_clause", "P", "a.sql")], ["a.sql"])
    text = _render_after([_found_in("authid_clause", "Q", "a.sql")], previous, ["a.sql"])
    assert "- [ ] `Q`" in text and "was:" not in text
