import csv
import json
import shutil
from pathlib import Path

import pytest

from ora2pg_gap_report import cli
from ora2pg_gap_report.cli import _expand_paths, main, resolve_format, scan_source

SAMPLES = Path(__file__).resolve().parents[1] / "docs" / "research" / "samples"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_resolve_format_explicit_choice_always_wins():
    assert resolve_format("json", None, True) == "json"
    assert resolve_format("markdown", None, False) == "markdown"


def test_resolve_format_defaults_to_terminal_on_an_interactive_tty():
    assert resolve_format(None, None, True) == "terminal"


def test_resolve_format_defaults_to_markdown_when_not_a_tty():
    assert resolve_format(None, None, False) == "markdown"


def test_resolve_format_defaults_to_markdown_when_writing_to_a_file_even_on_a_tty():
    # --output implies "for later reading / scripting", not an interactive
    # terminal session, regardless of what stdout happens to be.
    assert resolve_format(None, Path("report.md"), True) == "markdown"


def test_scan_source_runs_all_detectors_on_logger():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = scan_source(source)
    detectors_seen = {f.detector for f in findings}
    assert detectors_seen == {
        "autonomous_tx",
        "dbms_utl_calls",
        "bulk_collect",
        "conditional_compilation",
        "nested_subprogram",
        "package_state",
    }
    # autonomous_tx + dbms_utl_calls (verified in their own tests) +
    # bulk_collect: logger.pkb genuinely declares a local associative array
    # ('type ts_array is table of timestamp index by varchar2(100);') —
    # confirmed as a real, reproducible ora2pg gap on this exact snippet
    # (see docs/research/gap-003-bulk-collect-forall.md), not a synthetic-
    # only finding. conditional_compilation + nested_subprogram +
    # package_state: OraOpenSource/Logger makes heavy real-world use of all
    # three constructs (229 $IF/$ELSIF/$ELSE/$END directives gating version-
    # dependent code paths, 5 genuinely nested helper procedures/functions,
    # and 3 package-level session-state variables -- g_log_id, g_in_plugin_
    # error, g_running_timers) -- see each detector's own
    # test_real_open_source_logger_*() test for individual excerpts.
    assert len(findings) == 8 + 17 + 1 + 229 + 5 + 3


def test_scan_source_sorts_high_severity_first():
    source = (SAMPLES / "logger.pkb").read_text()
    findings = scan_source(source)
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s])


def test_main_end_to_end_markdown_to_stdout(capsys):
    exit_code = main([str(SAMPLES / "compound_trigger_apress.sql")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "TR_CONSTRUCTORS_CTI" in captured.out
    assert "Грубая оценка" in captured.out


def test_main_end_to_end_json_to_file(tmp_path):
    output_path = tmp_path / "report.json"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "json",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text())
    assert isinstance(data, list)
    object_names = {item["object_name"] for item in data}
    assert "TR_CONSTRUCTORS_CTI" in object_names
    assert "LOGGER.PURGE_ALL" in object_names


def test_main_end_to_end_csv_to_file(tmp_path):
    output_path = tmp_path / "report.csv"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "csv",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    rows = list(csv.DictReader(output_path.open(newline="", encoding="utf-8")))
    object_names = {row["object_name"] for row in rows}
    assert "TR_CONSTRUCTORS_CTI" in object_names
    assert "LOGGER.PURGE_ALL" in object_names


def test_main_end_to_end_sarif_to_file(tmp_path):
    output_path = tmp_path / "report.sarif"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "sarif",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    doc = json.loads(output_path.read_text())
    assert doc["version"] == "2.1.0"
    object_names = {
        r["message"]["text"] for r in doc["runs"][0]["results"]
    }  # sanity: results actually populated
    assert object_names
    assert doc["runs"][0]["tool"]["driver"]["rules"]


def test_main_end_to_end_html_to_file(tmp_path):
    output_path = tmp_path / "report.html"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "html",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    report = output_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in report.lower()
    assert "TR_CONSTRUCTORS_CTI" in report
    assert "LOGGER.PURGE_ALL" in report


def test_main_reports_missing_file_as_error(capsys):
    exit_code = main([str(SAMPLES / "does_not_exist.sql")])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "does_not_exist.sql" in captured.err


def test_main_reports_missing_file_with_brackets_in_path_without_crashing(
    tmp_path, capsys, monkeypatch
):
    # The path is printed through a rich Console; a path containing
    # brackets used to raise rich.errors.MarkupError instead of the
    # intended "file not found" message (paths are attacker/user-supplied
    # command-line input, not our own trusted markup). Wide COLUMNS so the
    # message isn't line-wrapped mid-path, which would make the substring
    # check below flaky independent of the bug being tested for.
    monkeypatch.setenv("COLUMNS", "200")
    bracket_path = tmp_path / "notes[/archive].sql"
    exit_code = main([str(bracket_path)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "notes[/archive].sql" in captured.err


def test_main_reports_unreadable_file_as_error_not_traceback(tmp_path, capsys, monkeypatch):
    # Simulate a read failure (e.g. permission denied) via monkeypatch
    # rather than chmod(0o000): chmod is a no-op against a root process
    # (as this sandbox runs), so it wouldn't actually reproduce the failure.
    unreadable = tmp_path / "secret.pkb"
    unreadable.write_text("create or replace package body x as end x; /")
    original_read_text = Path.read_text

    def boom(self, *args, **kwargs):
        if self == unreadable:
            raise PermissionError("Permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", boom)

    exit_code = main([str(unreadable)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert str(unreadable) in captured.err


def test_main_stamps_source_file_on_every_finding(tmp_path):
    output_path = tmp_path / "report.json"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "json",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text())
    by_object = {item["object_name"]: item["source_file"] for item in data}
    assert by_object["LOGGER.PURGE_ALL"].endswith("logger.pkb")
    assert by_object["TR_CONSTRUCTORS_CTI"].endswith("compound_trigger_apress.sql")


def test_check_connect_by_is_off_by_default_even_when_source_has_connect_by(monkeypatch):
    # Without --check-connect-by, ora2pg must never be invoked — the base
    # CLI stays a pure-Python, no-external-dependency tool.
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("run_estimate_cost should not be called without --check-connect-by")

    monkeypatch.setattr(cli, "run_estimate_cost", _should_not_be_called)
    exit_code = main([str(SAMPLES / "connect_by_hierarchy_pkg.sql")])
    assert exit_code == 0


def test_check_connect_by_reports_the_level_bug_via_mocked_ora2pg(monkeypatch, capsys):
    fixture_output = (FIXTURES / "ora2pg_generated_connect_by_hierarchy.sql").read_text()
    monkeypatch.setattr(cli, "run_estimate_cost", lambda *a, **k: fixture_output)

    exit_code = main(
        [str(SAMPLES / "connect_by_hierarchy_pkg.sql"), "--check-connect-by", "--format", "json"]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)

    assert exit_code == 0
    connect_by_findings = [d for d in data if d["detector"] == "connect_by"]
    assert len(connect_by_findings) == 1
    assert connect_by_findings[0]["snippet"].lower() == "c.level"
    # find_connect_by_risks() computes `line` against ora2pg's *generated*
    # output, not against connect_by_hierarchy_pkg.sql — stamping that
    # number onto source_file=connect_by_hierarchy_pkg.sql would point a
    # user at an unrelated line in their own file. 0 signals "not a line in
    # this file" instead of silently lying about which one it is.
    assert connect_by_findings[0]["line"] == 0
    assert connect_by_findings[0]["source_file"] == str(SAMPLES / "connect_by_hierarchy_pkg.sql")


def test_check_connect_by_warns_gracefully_when_ora2pg_not_found(capsys):
    exit_code = main(
        [
            str(SAMPLES / "connect_by_hierarchy_pkg.sql"),
            "--check-connect-by",
            "--ora2pg-bin",
            "definitely-not-a-real-binary",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0  # not finding ora2pg is a warning, not a hard error
    assert "ora2pg не найден" in captured.err


def test_check_connect_by_warning_is_english_when_lang_is_en(capsys):
    exit_code = main(
        [
            str(SAMPLES / "connect_by_hierarchy_pkg.sql"),
            "--check-connect-by",
            "--ora2pg-bin",
            "definitely-not-a-real-binary",
            "--lang",
            "en",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ora2pg wasn't found" in captured.err
    assert "не найден" not in captured.err


@pytest.mark.skipif(shutil.which("ora2pg") is None, reason="ora2pg not installed on PATH")
def test_check_connect_by_live_integration(capsys):
    exit_code = main(
        [str(SAMPLES / "connect_by_hierarchy_pkg.sql"), "--check-connect-by", "--format", "json"]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert exit_code == 0
    assert any(d["detector"] == "connect_by" for d in data)


def test_main_merges_and_resorts_findings_across_multiple_files(tmp_path):
    # file A: only a medium-severity dbms_utl_calls finding.
    # file B: a high-severity autonomous_tx finding.
    # Passed in an order where A's medium would print before B's high if
    # the per-file results were merely concatenated without re-sorting.
    file_a = tmp_path / "a_medium.pkb"
    file_a.write_text(
        """
        create or replace package body aaa_pkg as
          procedure foo is
          begin
            utl_file.fopen('DIR', 'f', 'r');
          end foo;
        end aaa_pkg;
        /
        """
    )
    file_b = tmp_path / "b_high.pkb"
    file_b.write_text(
        """
        create or replace package body bbb_pkg as
          procedure bar is
            pragma autonomous_transaction;
          begin
            commit;
          end bar;
        end bbb_pkg;
        /
        """
    )

    output_path = tmp_path / "report.json"
    exit_code = main(
        [str(file_a), str(file_b), "--format", "json", "--output", str(output_path)]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text())
    assert data[0]["severity"] == "high"
    assert data[0]["object_name"] == "BBB_PKG.BAR"
    assert data[-1]["severity"] == "medium"


def test_main_format_terminal_prints_a_styled_report_to_stdout(monkeypatch, capsys):
    # Fix a wide, deterministic width: the real detected terminal width
    # varies by environment, and the table intentionally ellipsis-truncates
    # long identifiers at narrow widths (see terminal_report.py) — that's
    # correct behaviour, not something this test should be sensitive to.
    monkeypatch.setenv("COLUMNS", "200")
    exit_code = main(
        [str(SAMPLES / "compound_trigger_apress.sql"), "--format", "terminal"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "TR_CONSTRUCTORS_CTI" in captured.out
    assert "Найдено проблемных объектов" in captured.out
    assert "Пояснения" in captured.out


def test_main_format_terminal_can_be_written_to_a_file(monkeypatch, tmp_path):
    monkeypatch.setenv("COLUMNS", "200")
    output_path = tmp_path / "report.txt"
    exit_code = main(
        [
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "terminal",
            "--output",
            str(output_path),
        ]
    )
    assert exit_code == 0
    text = output_path.read_text(encoding="utf-8")
    assert "TR_CONSTRUCTORS_CTI" in text
    # written to a real (non-tty) file: no raw ANSI escape codes
    assert "\x1b[" not in text


def test_main_format_terminal_reports_write_failure_without_a_traceback(capsys):
    # Same graceful-failure contract as the markdown/json --output path:
    # this used to have no try/except at all and crashed with a raw
    # traceback instead.
    exit_code = main(
        [
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "terminal",
            "--output",
            "/nonexistent-dir-xyz/out.txt",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Не удалось записать отчёт" in captured.err


def test_main_without_explicit_format_uses_markdown_under_pytest_capture(capsys):
    # capsys replaces sys.stdout with a non-tty stream, so this exercises
    # the same "not interactive" default path a redirected/piped run would.
    exit_code = main([str(SAMPLES / "compound_trigger_apress.sql")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.startswith("# Отчёт ora2pg-gap-report")


def test_severity_filter_only_shows_matching_findings(capsys):
    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--format", "json", "--severity", "medium"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert data
    assert {d["severity"] for d in data} == {"medium"}


def test_object_filter_matches_a_case_insensitive_substring(capsys):
    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--format", "json", "--object", "purge"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert data
    assert all("PURGE" in d["object_name"] for d in data)


def test_severity_and_object_filters_combine():
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            "--format",
            "json",
            "--severity",
            "high",
            "--object",
            "does-not-exist-anywhere",
        ]
    )
    assert exit_code == 0


def test_count_objects_counts_top_level_objects_not_nested_routines():
    source = (SAMPLES / "logger.pkb").read_text()
    # LOGGER is one PACKAGE BODY, however many procedures/functions it
    # declares inside — the package itself is the migration unit.
    assert cli.count_objects(source) == 1


def test_count_objects_counts_multiple_triggers_separately():
    source = (SAMPLES / "compound_trigger_dlee.sql").read_text()
    assert cli.count_objects(source) > 1


def test_count_objects_does_not_collapse_same_named_objects_in_different_schemas():
    # qualified_name_pattern() only captures the final (unqualified) name
    # component -- deduplicating by bare name used to silently collapse
    # hr.emp_pkg and sales.emp_pkg (two genuinely different migration
    # units) into one counted object.
    source = """
    CREATE OR REPLACE PACKAGE BODY hr.emp_pkg AS
      PROCEDURE noop IS BEGIN NULL; END noop;
    END emp_pkg;
    /
    CREATE OR REPLACE PACKAGE BODY sales.emp_pkg AS
      PROCEDURE noop IS BEGIN NULL; END noop;
    END emp_pkg;
    /
    CREATE OR REPLACE TRIGGER hr.log_error AFTER INSERT ON t BEGIN NULL; END;
    /
    CREATE OR REPLACE TRIGGER sales.log_error AFTER INSERT ON t BEGIN NULL; END;
    /
    """
    assert cli.count_objects(source) == 4


def test_count_objects_counts_a_view():
    source = "CREATE OR REPLACE VIEW active_customers AS SELECT * FROM customers WHERE active = 1;\n"
    assert cli.count_objects(source) == 1


def test_json_table_inside_a_view_is_attributed_not_unknown():
    # Found by scanning a real-world corpus (oracle-samples/
    # db-sample-schemas: customer_orders/co_create.sql) -- a JSON_TABLE
    # call inside a CREATE OR REPLACE VIEW used to attribute to 'UNKNOWN'
    # since a view was never a recognized attribution container.
    source = """
    CREATE OR REPLACE VIEW product_reviews AS
      SELECT r.rating
      FROM products p,
           JSON_TABLE(p.product_details, '$'
             COLUMNS (rating INTEGER PATH '$.rating')
           ) r;
    """
    findings = scan_source(source)
    json_table_findings = [f for f in findings if f.detector == "json_table"]
    assert len(json_table_findings) == 1
    assert json_table_findings[0].object_name == "PRODUCT_REVIEWS"


def test_version_flag_prints_the_installed_version_and_exits_cleanly(capsys):
    # argparse's action="version" raises SystemExit(0) after printing --
    # that's the documented, correct behaviour, not a crash.
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "ora2pg-gap-report" in captured.out


def test_expand_paths_recursively_finds_ddl_files_in_a_directory(tmp_path):
    nested = tmp_path / "schema" / "packages"
    nested.mkdir(parents=True)
    (tmp_path / "top.sql").write_text("create table t (id number);\n")
    (nested / "logger.pkb").write_text("create table t (id number);\n")
    (nested / "logger.pks").write_text("create table t (id number);\n")
    (nested / "readme.txt").write_text("not ddl\n")

    found, empty_dirs = _expand_paths([tmp_path])

    assert empty_dirs == []
    assert sorted(p.name for p in found) == ["logger.pkb", "logger.pks", "top.sql"]


def test_expand_paths_leaves_plain_files_and_missing_paths_untouched(tmp_path):
    real_file = tmp_path / "a.pkb"
    real_file.write_text("create table t (id number);\n")
    missing = tmp_path / "does_not_exist.sql"

    found, empty_dirs = _expand_paths([real_file, missing])

    assert found == [real_file, missing]
    assert empty_dirs == []


def test_expand_paths_matches_uppercase_extensions_too():
    # Exported DDL sometimes carries uppercase extensions (e.g. after
    # copying from Windows/case-preserving tooling) -- a directory listing
    # only lowercase-suffix files used to silently skip these.
    tmp_path_dir = Path(__file__).resolve().parent / "fixtures" / "_uppercase_ext_probe"
    tmp_path_dir.mkdir(exist_ok=True)
    try:
        (tmp_path_dir / "LOGGER.PKB").write_text("create table t (id number);\n")
        found, empty_dirs = _expand_paths([tmp_path_dir])
        assert empty_dirs == []
        assert [p.name for p in found] == ["LOGGER.PKB"]
    finally:
        shutil.rmtree(tmp_path_dir)


def test_expand_paths_deduplicates_a_file_reachable_both_directly_and_via_a_directory(tmp_path):
    # 'schema/ schema/logger.pkb' (directory plus an explicit path inside
    # it) is a natural invocation -- e.g. shell-completed or scripted --
    # and used to scan/report the same file twice, doubling every count.
    nested = tmp_path / "schema"
    nested.mkdir()
    dup_file = nested / "logger.pkb"
    dup_file.write_text("create table t (id number);\n")

    found, empty_dirs = _expand_paths([nested, dup_file])

    assert empty_dirs == []
    assert found == [dup_file]


def test_expand_paths_deduplicates_the_same_directory_listed_twice(tmp_path):
    nested = tmp_path / "schema"
    nested.mkdir()
    (nested / "logger.pkb").write_text("create table t (id number);\n")

    found, empty_dirs = _expand_paths([nested, nested])

    assert empty_dirs == []
    assert len(found) == 1


def test_main_does_not_double_count_a_file_reachable_two_ways(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    dup_path = schema_dir / "a.pkb"
    dup_path.write_text((SAMPLES / "logger.pkb").read_text(), encoding="utf-8")

    once_path = tmp_path / "once.json"
    main([str(dup_path), "--format", "json", "--output", str(once_path)])
    once = json.loads(once_path.read_text())

    twice_path = tmp_path / "twice.json"
    main([str(schema_dir), str(dup_path), "--format", "json", "--output", str(twice_path)])
    twice = json.loads(twice_path.read_text())

    assert len(twice) == len(once)
    assert len(once) > 0


def test_expand_paths_reports_a_directory_with_no_matching_files(tmp_path):
    empty = tmp_path / "no_ddl_here"
    empty.mkdir()
    (empty / "readme.txt").write_text("not ddl\n")

    found, empty_dirs = _expand_paths([empty])

    assert found == []
    assert empty_dirs == [empty]


def test_main_scans_a_directory_end_to_end(tmp_path):
    (tmp_path / "a.pkb").write_text(
        (SAMPLES / "logger.pkb").read_text(), encoding="utf-8"
    )
    output_path = tmp_path / "report.json"
    exit_code = main([str(tmp_path), "--format", "json", "--output", str(output_path)])
    assert exit_code == 0
    findings = json.loads(output_path.read_text())
    assert len(findings) > 0
    assert findings[0]["source_file"].endswith("a.pkb")


def test_main_warns_on_a_directory_with_no_matching_files(tmp_path, capsys):
    empty_dir = tmp_path / "no_ddl_here"
    empty_dir.mkdir()
    exit_code = main([str(empty_dir), "--format", "json"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "no_ddl_here" in captured.err
    assert json.loads(captured.out) == []


def test_main_save_writes_a_baseline_snapshot(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--format", "json", "--save", str(baseline_path)]
    )
    assert exit_code == 0
    saved = json.loads(baseline_path.read_text())
    assert saved["schema_version"] == 1
    assert len(saved["findings"]) > 0
    assert all("group_key" in rec for rec in saved["findings"])


def test_main_save_captures_all_findings_regardless_of_display_filters(tmp_path):
    # --save is meant as ground truth for the schema -- an unrelated
    # --severity filter narrowing what's *displayed* must not also shrink
    # what gets written to the baseline.
    baseline_path = tmp_path / "baseline.json"
    unfiltered_path = tmp_path / "unfiltered.json"
    main([str(SAMPLES / "logger.pkb"), "--format", "json", "--output", str(unfiltered_path)])
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            "--format",
            "json",
            "--severity",
            "low",
            "--save",
            str(baseline_path),
        ]
    )
    assert exit_code == 0
    unfiltered_count = len(json.loads(unfiltered_path.read_text()))
    saved_count = len(json.loads(baseline_path.read_text())["findings"])
    assert saved_count == unfiltered_count


def test_main_baseline_reports_no_new_or_resolved_against_an_identical_scan(tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    main([str(SAMPLES / "logger.pkb"), "--format", "json", "--save", str(baseline_path)])

    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--format", "json", "--baseline", str(baseline_path)]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NEW" in captured.err and "RESOLVED" in captured.err and "UNCHANGED" in captured.err
    assert "Новые находки" not in captured.err


def test_main_baseline_detects_new_and_resolved_findings(tmp_path, capsys):
    baseline_path = tmp_path / "baseline.json"
    main([str(SAMPLES / "logger.pkb"), "--format", "json", "--save", str(baseline_path)])

    # A different file's findings won't match logger.pkb's at all: every
    # baseline finding should show up RESOLVED, every new-scan finding NEW.
    exit_code = main(
        [
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "json",
            "--baseline",
            str(baseline_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Новые находки" in captured.err


def test_main_baseline_missing_file_is_a_graceful_error(tmp_path, capsys):
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            "--format",
            "json",
            "--baseline",
            str(tmp_path / "does_not_exist.json"),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "does_not_exist.json" in captured.err


def test_main_fail_on_high_fails_when_a_high_finding_exists(capsys):
    exit_code = main([str(SAMPLES / "logger.pkb"), "--format", "json", "--fail-on", "high"])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Migration gate FAILED" in captured.err


def test_main_fail_on_ignores_an_unrelated_severity_display_filter():
    # --severity low narrows the *displayed* report, but --fail-on high
    # must still see the real high-severity findings underneath it.
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            "--format",
            "json",
            "--severity",
            "low",
            "--fail-on",
            "high",
        ]
    )
    assert exit_code == 1


def test_main_fail_on_passes_when_no_qualifying_findings_exist(tmp_path):
    empty_source = tmp_path / "empty.sql"
    empty_source.write_text("create table t (id number);\n")
    exit_code = main([str(empty_source), "--format", "json", "--fail-on", "high"])
    assert exit_code == 0


def test_main_fail_on_defers_to_execution_errors(tmp_path):
    # A missing/unreadable file is a more fundamental problem than a gate
    # failure -- exit code 2 (execution error) must win over 1 (gate).
    exit_code = main(
        [str(tmp_path / "does_not_exist.sql"), "--format", "json", "--fail-on", "high"]
    )
    assert exit_code == 2


def test_main_explain_prints_the_research_doc_and_exits_cleanly(capsys):
    exit_code = main(["--explain", "GAP-023"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GAP-023" in captured.out
    assert "oracle_text" in captured.out
    assert "Oracle Text" in captured.out


def test_main_explain_prints_the_confirmed_version_stamp(capsys):
    exit_code = main(["--explain", "GAP-023"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ora2pg 25.0" in captured.out
    assert "PostgreSQL 16" in captured.out


def test_main_explain_prints_failure_stage_when_set(capsys):
    # GAP-031 is one of the trial batch with failure_stage populated (see
    # gap_registry.py) -- deployment.
    exit_code = main(["--explain", "GAP-031"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Когда ломается: развёртывание" in captured.out


def test_main_explain_prints_failure_stage_in_english(capsys):
    exit_code = main(["--explain", "GAP-031", "--lang", "en"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Fails at: deployment" in captured.out


def test_main_explain_omits_failure_stage_line_when_unset(capsys):
    # GAP-009 (object_type) has no failure_stage on purpose -- its finding
    # is a missing --estimate_cost number, not a code-shape/runtime issue,
    # same class of exception as autonomous_tx (see gap_registry.py). No
    # line at all, not an empty/placeholder one.
    exit_code = main(["--explain", "GAP-009"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Когда ломается" not in captured.out


def test_main_explain_accepts_a_bare_number(capsys):
    exit_code = main(["--explain", "23"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "GAP-023" in captured.out


def test_main_explain_unknown_gap_is_a_graceful_error(capsys):
    exit_code = main(["--explain", "GAP-999"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Неизвестный GAP" in captured.err


def test_main_explain_does_not_require_any_paths():
    # --explain is a standalone lookup -- it must work with no positional
    # paths argument at all, unlike a normal scan.
    exit_code = main(["--explain", "GAP-001"])
    assert exit_code == 0


def test_main_with_no_paths_and_no_explain_is_a_graceful_error(capsys):
    exit_code = main([])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--explain" in captured.err


def test_main_explain_combined_with_fail_on_is_rejected_not_silently_ignored(capsys):
    # --explain must not let a stray flag combination silently bypass a
    # real gate: a scan that would otherwise fail --fail-on high must not
    # exit 0 just because --explain was also passed.
    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--fail-on", "high", "--explain", "GAP-023"]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--explain" in captured.err


def test_main_explain_combined_with_save_is_rejected_and_writes_nothing(tmp_path):
    baseline_path = tmp_path / "should_not_exist.json"
    exit_code = main(["--explain", "GAP-023", "--save", str(baseline_path)])
    assert exit_code == 2
    assert not baseline_path.exists()


def test_main_explain_combined_with_paths_is_rejected(capsys):
    exit_code = main([str(SAMPLES / "logger.pkb"), "--explain", "GAP-023"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--explain" in captured.err


def test_main_explain_combined_with_verify_is_rejected(capsys):
    # Regression test: --explain is dispatched before --verify inside
    # main(), and its own conflict check used to list every other
    # standalone-incompatible flag except --verify -- so
    # `--explain GAP-NNN --verify` silently ran --explain and dropped
    # --verify entirely instead of erroring, contradicting both flags'
    # own documented "these can't be combined" behavior.
    exit_code = main(["--explain", "GAP-023", "--verify"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--explain" in captured.err


def test_main_explain_falls_back_to_a_github_link_when_docs_are_not_packaged(monkeypatch, capsys):
    # docs/research/ isn't shipped in the installed wheel (see
    # gap_registry.py's module docstring) -- simulate that by making the
    # lookup return None, the same as it would for a real pip install.
    monkeypatch.setattr(cli, "research_doc_path", lambda gap: None)
    exit_code = main(["--explain", "GAP-023"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "github.com" in captured.out
    assert "gap-023-oracle-text.md" in captured.out


@pytest.fixture(autouse=True)
def _isolated_lang_config(tmp_path, monkeypatch):
    """Every cli.py test gets an empty i18n config directory and no
    ORA2PG_GAP_REPORT_LANG -- otherwise a --set-lang choice or env var set
    on the machine running the tests would silently change every other
    test in this file's default (Russian) output."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("ORA2PG_GAP_REPORT_LANG", raising=False)


def test_main_lang_flag_switches_output_to_english(capsys):
    exit_code = main(["--lang", "en", str(SAMPLES / "logger.pkb")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Rough manual-rework estimate" in captured.out
    assert "Грубая оценка" not in captured.out


def test_main_lang_flag_does_not_persist_across_runs(capsys):
    main(["--lang", "en", str(SAMPLES / "logger.pkb")])
    capsys.readouterr()
    exit_code = main([str(SAMPLES / "logger.pkb")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Грубая оценка" in captured.out


def test_main_env_var_switches_output_to_english(monkeypatch, capsys):
    monkeypatch.setenv("ORA2PG_GAP_REPORT_LANG", "en")
    exit_code = main([str(SAMPLES / "logger.pkb")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Rough manual-rework estimate" in captured.out


def test_main_explain_respects_lang_flag(capsys):
    exit_code = main(["--lang", "en", "--explain", "GAP-023"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Confirmed on: ora2pg" in captured.out


def test_main_uses_a_previously_saved_lang_choice(capsys):
    from ora2pg_gap_report import i18n

    i18n.save_language("en")
    exit_code = main([str(SAMPLES / "logger.pkb")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Rough manual-rework estimate" in captured.out


def test_main_set_lang_saves_the_choice_and_exits(monkeypatch, capsys):
    from ora2pg_gap_report import i18n

    monkeypatch.setattr(i18n, "prompt_language_interactively", lambda *a, **k: "en")
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    exit_code = main(["--set-lang"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert i18n.get_saved_language() == "en"
    assert "Saved" in captured.out


def test_main_set_lang_fails_cleanly_without_a_real_terminal(monkeypatch, capsys):
    # Regression test: --set-lang used to call the interactive picker
    # unconditionally, which raised an uncaught EOFError (raw Python
    # traceback) whenever stdin wasn't a real terminal -- e.g. a cron job,
    # a CI step, `< /dev/null`. It must fail the same clean way every
    # other unsupported-usage error in this CLI does: a red message on
    # stderr and exit code 2, no traceback.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    exit_code = main(["--set-lang"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "терминал" in captured.err


# --verify -----------------------------------------------------------------

_ORACLE_CROSS_APPLY_SOURCE = """
CREATE OR REPLACE PACKAGE BODY report_pkg IS
  FUNCTION get_tree(p_id NUMBER) RETURN VARCHAR2 IS
    v_result VARCHAR2(4000);
  BEGIN
    SELECT a.name INTO v_result
    FROM employees a
    CROSS APPLY (SELECT name FROM departments d WHERE d.id = a.dept_id) b;
    RETURN v_result;
  END;
END report_pkg;
/
"""

_GENERATED_STILL_BROKEN = """
CREATE OR REPLACE FUNCTION report_pkg.get_tree(p_id numeric) RETURNS varchar AS $$
BEGIN
  SELECT a.name INTO v_result
  FROM employees a
  CROSS APPLY (SELECT name FROM departments d WHERE d.id = a.dept_id) b;
END;
$$ LANGUAGE plpgsql;
"""

_GENERATED_FIXED = """
CREATE OR REPLACE FUNCTION report_pkg.get_tree(p_id numeric) RETURNS varchar AS $$
BEGIN
  SELECT a.name INTO v_result
  FROM employees a
  JOIN LATERAL (SELECT name FROM departments d WHERE d.id = a.dept_id) b ON true;
END;
$$ LANGUAGE plpgsql;
"""


def _save_cross_apply_baseline(tmp_path) -> Path:
    oracle_file = tmp_path / "oracle_schema.sql"
    oracle_file.write_text(_ORACLE_CROSS_APPLY_SOURCE)
    baseline_path = tmp_path / "baseline.json"
    # --output here is just to keep this helper's own report off stdout --
    # callers frequently assert on captured.out for the *next* main()
    # call, and this scan's own JSON dump would otherwise leak into it.
    scan_report_path = tmp_path / "_discard_scan_report.json"
    exit_code = main(
        [str(oracle_file), "--save", str(baseline_path), "--format", "json", "--output", str(scan_report_path)]
    )
    assert exit_code == 0
    return baseline_path


def test_verify_reports_still_present_when_the_pattern_survives_in_generated_code(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN)

    exit_code = main(["--verify", "--baseline", str(baseline_path), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "STILL_PRESENT" in captured.out
    assert "cross_apply" in captured.out
    assert "GAP-022" in captured.out


def test_verify_reports_not_detected_when_the_pattern_is_gone_from_generated_code(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_FIXED)

    exit_code = main(["--verify", "--baseline", str(baseline_path), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NOT_DETECTED" in captured.out
    assert "STILL_PRESENT" not in captured.out


def test_verify_json_output(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN)

    exit_code = main(
        ["--verify", "--baseline", str(baseline_path), "--format", "json", str(generated)]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)
    assert data["baseline_detectors"] == 1
    assert data["still_present"] == 1
    assert data["results"][0]["detector"] == "cross_apply"
    assert data["results"][0]["status"] == "still_present"


def test_verify_reports_not_verifiable_for_a_dropped_construct_detector(tmp_path, capsys):
    oracle_file = tmp_path / "oracle_schema.sql"
    oracle_file.write_text(
        "CREATE TABLE audit_log (log_id NUMBER, message VARCHAR2(200)) READ ONLY;\n"
    )
    baseline_path = tmp_path / "baseline.json"
    scan_report_path = tmp_path / "_discard_scan_report.json"
    assert main(
        [str(oracle_file), "--save", str(baseline_path), "--format", "json", "--output", str(scan_report_path)]
    ) == 0

    # Whatever the generated table looks like, read_only_table is
    # NOT_VERIFIABLE by construction: ora2pg drops READ ONLY from every
    # migration's output, so its presence/absence in the generated file
    # proves nothing either way.
    generated = tmp_path / "generated.sql"
    generated.write_text("CREATE TABLE audit_log (log_id bigint, message varchar(200));\n")

    exit_code = main(["--verify", "--baseline", str(baseline_path), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NOT_VERIFIABLE" in captured.out


def test_verify_requires_baseline(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN)
    exit_code = main(["--verify", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--baseline" in captured.err


def test_verify_rejects_conflicting_flags(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN)

    exit_code = main(
        ["--verify", "--baseline", str(baseline_path), "--fail-on", "high", str(generated)]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--verify" in captured.err


def test_verify_rejects_unsupported_format(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN)

    exit_code = main(
        ["--verify", "--baseline", str(baseline_path), "--format", "html", str(generated)]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--format" in captured.err


def test_verify_can_write_to_a_file(tmp_path):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN)
    output_path = tmp_path / "verification.json"

    exit_code = main(
        [
            "--verify",
            "--baseline",
            str(baseline_path),
            "--format",
            "json",
            "--output",
            str(output_path),
            str(generated),
        ]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text())
    assert data["results"][0]["status"] == "still_present"


def test_verify_english_output(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN)

    exit_code = main(
        ["--verify", "--baseline", str(baseline_path), "--lang", "en", str(generated)]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Post-migration verification" in captured.out
    assert "Проверка после миграции" not in captured.out


def test_tui_rejects_being_combined_with_fail_on(capsys):
    exit_code = main(["--tui", "--fail-on", "high", str(SAMPLES)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--tui" in captured.err


def test_tui_rejects_more_than_one_path(capsys):
    exit_code = main(["--tui", str(SAMPLES / "compound_trigger_apress.sql"), str(SAMPLES / "file_util_pkg.pkb")])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--tui" in captured.err


def test_tui_rejects_a_nonexistent_path(tmp_path, capsys):
    missing = tmp_path / "does_not_exist"
    exit_code = main(["--tui", str(missing)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert str(missing) in captured.err


def test_tui_reports_a_clean_error_when_textual_is_not_installed(monkeypatch, capsys):
    # Simulates an install without the [tui] extra: setting a module to
    # None in sys.modules makes `import` raise ImportError for it, without
    # needing textual to be genuinely absent from this test environment.
    import sys

    monkeypatch.setitem(sys.modules, "ora2pg_gap_report.tui_app", None)
    exit_code = main(["--tui", str(SAMPLES)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "textual" in captured.err
    assert "pip install" in captured.err


def test_tui_launches_with_the_given_directory_as_the_start_path(monkeypatch):
    calls = []
    import ora2pg_gap_report.tui_app as tui_app

    monkeypatch.setattr(tui_app, "run_tui", lambda start_path=None: calls.append(start_path))
    exit_code = main(["--tui", str(SAMPLES)])
    assert exit_code == 0
    assert calls == [SAMPLES]


def test_tui_with_no_path_uses_cwd(monkeypatch):
    calls = []
    import ora2pg_gap_report.tui_app as tui_app

    monkeypatch.setattr(tui_app, "run_tui", lambda start_path=None: calls.append(start_path))
    exit_code = main(["--tui"])
    assert exit_code == 0
    assert calls == [None]


def test_tui_with_a_file_path_starts_the_tree_at_its_parent_directory(monkeypatch):
    calls = []
    import ora2pg_gap_report.tui_app as tui_app

    monkeypatch.setattr(tui_app, "run_tui", lambda start_path=None: calls.append(start_path))
    target = SAMPLES / "compound_trigger_apress.sql"
    exit_code = main(["--tui", str(target)])
    assert exit_code == 0
    assert calls == [target.parent]
