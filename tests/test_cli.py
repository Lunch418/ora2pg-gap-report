import csv
import json
import shutil
from pathlib import Path

import pytest

from ora2pg_gap_report import cli, core
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
    source = (SAMPLES / "logger.pkb").read_text(encoding="utf-8")
    findings = scan_source(source)
    detectors_seen = {f.detector for f in findings}
    assert detectors_seen == {
        "autonomous_tx",
        "dbms_utl_calls",
        "bulk_collect",
        "conditional_compilation",
        "nested_subprogram",
        "package_state",
        "pragma_exception_init",
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
    # and 25 package-level session-state declarations -- 3 plain variables
    # (g_log_id, g_in_plugin_error, g_running_timers) plus 22 package-level
    # CONSTANTs (gc_line_feed, gc_pref_* and friends) -- see each detector's
    # own test_real_open_source_logger_*() test for individual excerpts.
    # The CONSTANT count went from undetected to 22 real findings the
    # moment package_state.py's grammar covered CONSTANT (see
    # docs/research/gap-036-package-state.md's addendum) -- this file was
    # already in the corpus the whole time, just silently under-counted.
    # pragma_exception_init: one real declaration at line 299,
    # 'pragma exception_init(invalid_userenv_parm, -2003)', paired with a
    # WHEN handler further down -- exactly the shape GAP-060 is about, so
    # after conversion that handler would catch a SQLSTATE PostgreSQL never
    # raises. Found by running the new detector over the corpus, not
    # constructed for the test.
    assert len(findings) == 8 + 17 + 1 + 229 + 5 + 25 + 1


def test_scan_source_sorts_high_severity_first():
    source = (SAMPLES / "logger.pkb").read_text(encoding="utf-8")
    findings = scan_source(source)
    severities = [f.severity for f in findings]
    assert severities == sorted(severities, key=lambda s: {"high": 0, "medium": 1, "low": 2}[s])


def test_help_text_is_rendered_in_english_when_lang_en_is_passed_before_help(capsys):
    # argparse's --help exits (SystemExit) as soon as it sees -h/--help --
    # the language has to be resolved from raw argv *before* the parser is
    # even built (see cli.py's _peek_lang_for_help()), not from the parsed
    # Namespace, which never gets produced on a --help exit.
    with pytest.raises(SystemExit):
        main(["--lang", "en", "--help"])
    captured = capsys.readouterr()
    assert "Scans exported Oracle DDL" in captured.out
    assert "Сканирует выгруженный" not in captured.out


def test_help_text_defaults_to_russian_without_an_explicit_lang(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    captured = capsys.readouterr()
    assert "Сканирует выгруженный" in captured.out


def test_help_text_recognizes_the_equals_sign_form_of_lang(capsys):
    with pytest.raises(SystemExit):
        main(["--lang=en", "--help"])
    captured = capsys.readouterr()
    assert "Scans exported Oracle DDL" in captured.out


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
    data = json.loads(output_path.read_text(encoding="utf-8"))["findings"]
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
    doc = json.loads(output_path.read_text(encoding="utf-8"))
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
    # str(bracket_path), not the literal "notes[/archive].sql": "/" is a
    # separator on Windows too, so the same Path renders with a backslash
    # there and a hardcoded POSIX spelling never matches. What matters for
    # this test is the brackets surviving Rich, not the separator.
    assert str(bracket_path) in captured.err


def test_main_reports_unreadable_file_as_error_not_traceback(tmp_path, capsys, monkeypatch):
    # Simulate a read failure (e.g. permission denied) via monkeypatch
    # rather than chmod(0o000): chmod is a no-op against a root process
    # (as this sandbox runs), so it wouldn't actually reproduce the failure.
    unreadable = tmp_path / "secret.pkb"
    unreadable.write_text("create or replace package body x as end x; /", encoding="utf-8")
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
    data = json.loads(output_path.read_text(encoding="utf-8"))["findings"]
    by_object = {item["object_name"]: item["source_file"] for item in data}
    assert by_object["LOGGER.PURGE_ALL"].endswith("logger.pkb")
    assert by_object["TR_CONSTRUCTORS_CTI"].endswith("compound_trigger_apress.sql")


def test_check_connect_by_is_off_by_default_even_when_source_has_connect_by(monkeypatch):
    # Without --check-connect-by, ora2pg must never be invoked — the base
    # CLI stays a pure-Python, no-external-dependency tool.
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("run_estimate_cost should not be called without --check-connect-by")

    monkeypatch.setattr(core, "run_estimate_cost", _should_not_be_called)
    exit_code = main([str(SAMPLES / "connect_by_hierarchy_pkg.sql")])
    assert exit_code == 0


def test_check_connect_by_reports_the_level_bug_via_mocked_ora2pg(monkeypatch, capsys):
    fixture_output = (FIXTURES / "ora2pg_generated_connect_by_hierarchy.sql").read_text(encoding="utf-8")
    monkeypatch.setattr(core, "run_estimate_cost", lambda *a, **k: fixture_output)

    exit_code = main(
        [str(SAMPLES / "connect_by_hierarchy_pkg.sql"), "--check-connect-by", "--format", "json"]
    )
    captured = capsys.readouterr()
    data = json.loads(captured.out)["findings"]

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
    data = json.loads(captured.out)["findings"]
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
    , encoding="utf-8")
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
    , encoding="utf-8")

    output_path = tmp_path / "report.json"
    exit_code = main(
        [str(file_a), str(file_b), "--format", "json", "--output", str(output_path)]
    )
    assert exit_code == 0
    data = json.loads(output_path.read_text(encoding="utf-8"))["findings"]
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


def test_main_format_terminal_reports_write_failure_without_a_traceback(tmp_path, capsys):
    # Same graceful-failure contract as the markdown/json --output path:
    # this used to have no try/except at all and crashed with a raw
    # traceback instead. The unwritable path is one *under an existing
    # regular file*, not just a missing directory -- a missing directory
    # is created now rather than being an error (see atomic_write.py).
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    exit_code = main(
        [
            str(SAMPLES / "compound_trigger_apress.sql"),
            "--format",
            "terminal",
            "--output",
            str(blocker / "out.txt"),
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
    data = json.loads(captured.out)["findings"]
    assert data
    assert {d["severity"] for d in data} == {"medium"}


def test_object_filter_matches_a_case_insensitive_substring(capsys):
    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--format", "json", "--object", "purge"]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    data = json.loads(captured.out)["findings"]
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
    source = (SAMPLES / "logger.pkb").read_text(encoding="utf-8")
    # LOGGER is one PACKAGE BODY, however many procedures/functions it
    # declares inside — the package itself is the migration unit.
    assert cli.count_objects(source) == 1


def test_count_objects_counts_multiple_triggers_separately():
    source = (SAMPLES / "compound_trigger_dlee.sql").read_text(encoding="utf-8")
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
    (tmp_path / "top.sql").write_text("create table t (id number);\n", encoding="utf-8")
    (nested / "logger.pkb").write_text("create table t (id number);\n", encoding="utf-8")
    (nested / "logger.pks").write_text("create table t (id number);\n", encoding="utf-8")
    (nested / "readme.txt").write_text("not ddl\n", encoding="utf-8")

    found, empty_dirs = _expand_paths([tmp_path])

    assert empty_dirs == []
    assert sorted(p.name for p in found) == ["logger.pkb", "logger.pks", "top.sql"]


def test_expand_paths_leaves_plain_files_and_missing_paths_untouched(tmp_path):
    real_file = tmp_path / "a.pkb"
    real_file.write_text("create table t (id number);\n", encoding="utf-8")
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
        (tmp_path_dir / "LOGGER.PKB").write_text("create table t (id number);\n", encoding="utf-8")
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
    dup_file.write_text("create table t (id number);\n", encoding="utf-8")

    found, empty_dirs = _expand_paths([nested, dup_file])

    assert empty_dirs == []
    assert found == [dup_file]


def test_expand_paths_deduplicates_the_same_directory_listed_twice(tmp_path):
    nested = tmp_path / "schema"
    nested.mkdir()
    (nested / "logger.pkb").write_text("create table t (id number);\n", encoding="utf-8")

    found, empty_dirs = _expand_paths([nested, nested])

    assert empty_dirs == []
    assert len(found) == 1


def test_main_does_not_double_count_a_file_reachable_two_ways(tmp_path):
    schema_dir = tmp_path / "schema"
    schema_dir.mkdir()
    dup_path = schema_dir / "a.pkb"
    dup_path.write_text((SAMPLES / "logger.pkb").read_text(encoding="utf-8"), encoding="utf-8")

    once_path = tmp_path / "once.json"
    main([str(dup_path), "--format", "json", "--output", str(once_path)])
    once = json.loads(once_path.read_text(encoding="utf-8"))

    twice_path = tmp_path / "twice.json"
    main([str(schema_dir), str(dup_path), "--format", "json", "--output", str(twice_path)])
    twice = json.loads(twice_path.read_text(encoding="utf-8"))

    assert len(twice) == len(once)
    assert len(once) > 0


def test_expand_paths_reports_a_directory_with_no_matching_files(tmp_path):
    empty = tmp_path / "no_ddl_here"
    empty.mkdir()
    (empty / "readme.txt").write_text("not ddl\n", encoding="utf-8")

    found, empty_dirs = _expand_paths([empty])

    assert found == []
    assert empty_dirs == [empty]


def test_main_scans_a_directory_end_to_end(tmp_path):
    (tmp_path / "a.pkb").write_text(
        (SAMPLES / "logger.pkb").read_text(encoding="utf-8"), encoding="utf-8"
    )
    output_path = tmp_path / "report.json"
    exit_code = main([str(tmp_path), "--format", "json", "--output", str(output_path)])
    assert exit_code == 0
    findings = json.loads(output_path.read_text(encoding="utf-8"))["findings"]
    assert len(findings) > 0
    assert findings[0]["source_file"].endswith("a.pkb")


def test_main_warns_on_a_directory_with_no_matching_files(tmp_path, capsys):
    empty_dir = tmp_path / "no_ddl_here"
    empty_dir.mkdir()
    exit_code = main([str(empty_dir), "--format", "json"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "no_ddl_here" in captured.err
    assert json.loads(captured.out)["findings"] == []


def test_main_save_writes_a_baseline_snapshot(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--format", "json", "--save", str(baseline_path)]
    )
    assert exit_code == 0
    saved = json.loads(baseline_path.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 3
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
    # Two different envelopes: the report keys its findings under
    # "findings" alongside the shared message table, the baseline under
    # "findings" alongside its own schema_version.
    unfiltered_count = len(json.loads(unfiltered_path.read_text(encoding="utf-8"))["findings"])
    saved_count = len(json.loads(baseline_path.read_text(encoding="utf-8"))["findings"])
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


def test_main_save_and_baseline_pointing_at_the_same_file_is_rejected(tmp_path, capsys):
    # --baseline reads a *previous* run's snapshot to diff against --
    # pointing both flags at the same path means --baseline reads back
    # the file --save is about to overwrite with this run's own result,
    # comparing the run against itself (always "nothing changed") instead
    # of erroring on a request that can never do what it looks like it
    # asks for.
    same_path = tmp_path / "baseline.json"
    exit_code = main(
        [str(SAMPLES / "logger.pkb"), "--save", str(same_path), "--baseline", str(same_path)]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--save" in captured.err and "--baseline" in captured.err
    assert not same_path.exists()


def test_main_save_and_baseline_same_file_via_different_spellings_is_still_rejected(tmp_path, capsys):
    # Comparing resolved paths, not raw strings -- "./x.json" and "x.json"
    # (or a path through a symlink) are the same file on disk even though
    # they don't compare equal as strings.
    real_path = tmp_path / "baseline.json"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            "--save",
            str(real_path),
            "--baseline",
            str(tmp_path / "." / "baseline.json"),
        ]
    )
    assert exit_code == 2
    assert not real_path.exists()


def test_main_save_is_skipped_when_the_scan_was_partial(tmp_path, capsys):
    # A snapshot missing some of what was asked to be scanned isn't
    # "ground truth for the schema" -- writing it anyway would make the
    # next --baseline diff report those files' findings as NEW the moment
    # the actual problem (why they were skipped) gets fixed, not as what
    # they really are: never captured in the first place.
    baseline_path = tmp_path / "baseline.json"
    exit_code = main(
        [
            str(SAMPLES / "logger.pkb"),
            str(tmp_path / "does_not_exist.sql"),
            "--save",
            str(baseline_path),
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert not baseline_path.exists()
    assert "не сохранён" in captured.err


def test_main_explain_rejects_format_output_severity_object_too(tmp_path, capsys):
    # --fail-on/--save/--baseline/--check-connect-by were already rejected
    # -- --format/--output/--severity/--object used to be silently
    # ignored instead: --explain would print to stdout as normal and
    # never touch --output at all, with no indication the other flags did
    # nothing.
    out_path = tmp_path / "should_not_be_created.md"
    for extra in (
        ["--output", str(out_path)],
        ["--format", "json"],
        ["--severity", "high"],
        ["--object", "X"],
    ):
        exit_code = main(["--explain", "GAP-001", *extra])
        captured = capsys.readouterr()
        assert exit_code == 2, extra
        assert "нельзя" in captured.err, extra
    assert not out_path.exists()


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
    empty_source.write_text("create table t (id number);\n", encoding="utf-8")
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


def test_main_explain_prints_severity(capsys):
    # GAP-023 (oracle_text) is high severity -- shown uppercased, same as
    # the terminal report's own severity styling elsewhere.
    exit_code = main(["--explain", "GAP-023"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Severity: HIGH" in captured.out


def test_main_explain_prints_severity_for_a_medium_gap(capsys):
    # GAP-015 (context_object) is one of the four medium-severity gaps.
    exit_code = main(["--explain", "GAP-015"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Severity: MEDIUM" in captured.out


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
    oracle_file.write_text(_ORACLE_CROSS_APPLY_SOURCE, encoding="utf-8")
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
    generated.write_text(_GENERATED_STILL_BROKEN, encoding="utf-8")

    exit_code = main(["--verify", "--baseline", str(baseline_path), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "STILL_PRESENT" in captured.out
    assert "cross_apply" in captured.out
    assert "GAP-022" in captured.out


def test_verify_reports_not_detected_when_the_pattern_is_gone_from_generated_code(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_FIXED, encoding="utf-8")

    exit_code = main(["--verify", "--baseline", str(baseline_path), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NOT_DETECTED" in captured.out
    assert "STILL_PRESENT" not in captured.out


def test_verify_json_output(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN, encoding="utf-8")

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
    , encoding="utf-8")
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
    generated.write_text("CREATE TABLE audit_log (log_id bigint, message varchar(200));\n", encoding="utf-8")

    exit_code = main(["--verify", "--baseline", str(baseline_path), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "NOT_VERIFIABLE" in captured.out


def test_verify_requires_baseline(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN, encoding="utf-8")
    exit_code = main(["--verify", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--baseline" in captured.err


def test_verify_rejects_conflicting_flags(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN, encoding="utf-8")

    exit_code = main(
        ["--verify", "--baseline", str(baseline_path), "--fail-on", "high", str(generated)]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--verify" in captured.err


def test_verify_rejects_unsupported_format(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN, encoding="utf-8")

    exit_code = main(
        ["--verify", "--baseline", str(baseline_path), "--format", "html", str(generated)]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--format" in captured.err


def test_verify_can_write_to_a_file(tmp_path):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN, encoding="utf-8")
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
    data = json.loads(output_path.read_text(encoding="utf-8"))
    assert data["results"][0]["status"] == "still_present"


def test_verify_english_output(tmp_path, capsys):
    baseline_path = _save_cross_apply_baseline(tmp_path)
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_STILL_BROKEN, encoding="utf-8")

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

    monkeypatch.setattr(tui_app, "run_tui", lambda start_path=None, lang=None: calls.append(start_path))
    exit_code = main(["--tui", str(SAMPLES)])
    assert exit_code == 0
    assert calls == [SAMPLES]


def test_tui_with_no_path_uses_cwd(monkeypatch):
    calls = []
    import ora2pg_gap_report.tui_app as tui_app

    monkeypatch.setattr(tui_app, "run_tui", lambda start_path=None, lang=None: calls.append(start_path))
    exit_code = main(["--tui"])
    assert exit_code == 0
    assert calls == [None]


def test_tui_with_a_file_path_starts_the_tree_at_its_parent_directory(monkeypatch):
    calls = []
    import ora2pg_gap_report.tui_app as tui_app

    monkeypatch.setattr(tui_app, "run_tui", lambda start_path=None, lang=None: calls.append(start_path))
    target = SAMPLES / "compound_trigger_apress.sql"
    exit_code = main(["--tui", str(target)])
    assert exit_code == 0
    assert calls == [target.parent]


_GENERATED_IDENTITY_BUG = (
    "CREATE TABLE foo (\n"
    "    id integer GENERATED ALWAYS AS IDENTITY ((START WITH 1 INCREMENT BY 1)),\n"
    "    name text\n"
    ");\n"
)


def test_fix_dry_run_prints_a_diff_and_does_not_touch_the_file(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_IDENTITY_BUG, encoding="utf-8")

    exit_code = main(["--fix", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "-    id integer GENERATED ALWAYS AS IDENTITY ((START WITH 1 INCREMENT BY 1))" in captured.out
    assert "+    id integer GENERATED ALWAYS AS IDENTITY (START WITH 1 INCREMENT BY 1)" in captured.out
    assert generated.read_text(encoding="utf-8") == _GENERATED_IDENTITY_BUG


def test_fix_write_actually_rewrites_the_file(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_IDENTITY_BUG, encoding="utf-8")

    exit_code = main(["--fix", "--write", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "((" not in generated.read_text(encoding="utf-8")
    assert "IDENTITY (START WITH 1 INCREMENT BY 1)" in generated.read_text(encoding="utf-8")
    assert "записано" in captured.err


def test_fix_reports_clean_when_nothing_to_fix(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text("CREATE TABLE foo (id integer, name text);\n", encoding="utf-8")

    exit_code = main(["--fix", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "исправлений не найдено" in captured.err


def test_fix_dry_run_diff_is_not_wrapped_and_is_git_apply_clean(tmp_path, capsys):
    # Regression guard for A-01: Console.print() wraps text to the terminal
    # width (or a fixed 80 columns off a real tty), which corrupts a
    # unified diff -- a long path alone is enough to wrap its own "---"/
    # "+++" header line in two. stdout must carry nothing but the diff
    # difflib itself would produce, byte for byte, so `--fix > out.patch`
    # is always a valid patch regardless of how deep the scanned path is.
    long_dir = tmp_path / ("this_is_a_very_long_directory_name_" * 3)
    long_dir.mkdir()
    generated = long_dir / "generated.sql"
    generated.write_text(_GENERATED_IDENTITY_BUG, encoding="utf-8")

    exit_code = main(["--fix", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 0

    import difflib

    fixed = generated.read_text(encoding="utf-8").replace("((START WITH 1 INCREMENT BY 1))", "(START WITH 1 INCREMENT BY 1)")
    expected_diff = "".join(
        difflib.unified_diff(
            _GENERATED_IDENTITY_BUG.splitlines(keepends=True),
            fixed.splitlines(keepends=True),
            fromfile=str(generated),
            tofile=str(generated),
        )
    )
    assert captured.out == expected_diff
    # The specific corruption, spelled out: the `---` header carries the
    # full path and is the first thing Rich used to fold in two. It has to
    # survive as one line, however long the path is -- so the check is
    # "this exact line is present intact", not a length threshold (a
    # threshold just re-fails on any runner whose temp directory is long,
    # which is most of them).
    assert f"--- {generated}" in captured.out.splitlines()
    assert f"+++ {generated}" in captured.out.splitlines()


def test_write_without_fix_is_rejected(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_IDENTITY_BUG, encoding="utf-8")

    exit_code = main(["--write", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--fix" in captured.err
    assert generated.read_text(encoding="utf-8") == _GENERATED_IDENTITY_BUG


def test_fix_rejects_conflicting_flags(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_IDENTITY_BUG, encoding="utf-8")

    exit_code = main(["--fix", "--fail-on", "high", str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--fix" in captured.err


def test_fix_combined_with_verify_is_rejected(tmp_path, capsys):
    generated = tmp_path / "generated.sql"
    generated.write_text(_GENERATED_IDENTITY_BUG, encoding="utf-8")
    baseline_path = tmp_path / "baseline.json"
    baseline_path.write_text('{"schema_version": 3, "findings": [], "complete": true}', encoding="utf-8")

    exit_code = main(["--verify", "--fix", "--baseline", str(baseline_path), str(generated)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--verify" in captured.err


def test_fix_combined_with_tui_is_rejected(capsys):
    exit_code = main(["--tui", "--fix"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--tui" in captured.err


def test_fix_combined_with_explain_is_rejected(capsys):
    exit_code = main(["--explain", "GAP-028", "--fix"])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--explain" in captured.err


def test_fix_reports_missing_file_as_error(tmp_path, capsys):
    missing = tmp_path / "does_not_exist.sql"
    exit_code = main(["--fix", str(missing)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "does_not_exist.sql" in captured.err


def test_fix_requires_at_least_one_path(capsys):
    exit_code = main(["--fix"])
    capsys.readouterr()
    assert exit_code == 2


# --- A-05 regression: a detector crash on one file must not take down the
# whole scan, and must exit with a code distinct from --fail-on's 1. ---


def test_a_detector_crash_on_one_file_does_not_take_down_the_whole_scan(tmp_path, monkeypatch, capsys):
    original = core._DETECTORS_BY_DIALECT["oracle"]

    def flaky(source):
        if "CRASH_HERE" in source:
            raise RecursionError("simulated: unbounded recursion")
        return []

    monkeypatch.setitem(core._DETECTORS_BY_DIALECT, "oracle", (*original, flaky))

    bad = tmp_path / "bad.sql"
    bad.write_text("-- CRASH_HERE\nSELECT * FROM t CROSS APPLY (SELECT 1) x;\n", encoding="utf-8")
    good = tmp_path / "good.sql"
    good.write_text("SELECT * FROM u CROSS APPLY (SELECT 2) y;\n", encoding="utf-8")

    exit_code = main([str(bad), str(good), "--format", "json"])
    captured = capsys.readouterr()

    assert exit_code == 3
    assert "bad.sql" in captured.err
    assert "RecursionError" in captured.err

    findings = json.loads(captured.out)["findings"]
    # The other file scanned normally...
    assert any(f["source_file"] == str(good) for f in findings)
    # ...and so did every *other* detector on the file that crashed: what
    # was lost is the crashed detector's own findings, not the file's.
    assert any(f["source_file"] == str(bad) and f["detector"] == "cross_apply" for f in findings)


def test_the_crashed_detector_is_named_not_just_counted(tmp_path, monkeypatch, capsys):
    # "Which detector is broken" is the one thing a bug report needs.
    original = core._DETECTORS_BY_DIALECT["oracle"]

    def boom(source):
        raise RecursionError("simulated")

    boom.__module__ = "ora2pg_gap_report.detectors.pretend_detector"
    monkeypatch.setitem(core._DETECTORS_BY_DIALECT, "oracle", (*original, boom))

    source = tmp_path / "x.sql"
    source.write_text("SELECT 1;\n", encoding="utf-8")

    assert main([str(source)]) == 3
    assert "pretend_detector" in capsys.readouterr().err


def test_internal_error_exit_code_is_distinct_from_fail_on_gate_failed(tmp_path, monkeypatch, capsys):
    # The exact collision A-05 is about: an unhandled exception's default
    # exit code (1) used to be indistinguishable from --fail-on's "gate
    # failed" (also 1). It must win over --fail-on's own exit code too.
    original = core._DETECTORS_BY_DIALECT["oracle"]

    def boom(source):
        raise RecursionError("simulated")

    monkeypatch.setitem(core._DETECTORS_BY_DIALECT, "oracle", (*original, boom))

    source = tmp_path / "x.sql"
    source.write_text("READ ONLY;\n", encoding="utf-8")  # also trips read_only_table, so --fail-on has something to fail on

    exit_code = main([str(source), "--fail-on", "high"])
    assert exit_code == 3


def test_a_crash_blocks_save_the_same_way_a_skipped_file_does(tmp_path, monkeypatch, capsys):
    original = core._DETECTORS_BY_DIALECT["oracle"]

    def boom(source):
        raise RecursionError("simulated")

    monkeypatch.setitem(core._DETECTORS_BY_DIALECT, "oracle", (*original, boom))

    source = tmp_path / "x.sql"
    source.write_text("SELECT 1;\n", encoding="utf-8")
    baseline_path = tmp_path / "baseline.json"

    exit_code = main([str(source), "--save", str(baseline_path)])
    assert exit_code == 3
    assert not baseline_path.exists()


def test_an_unexpected_crash_outside_the_scan_loop_is_still_caught_at_the_top_level(
    tmp_path, monkeypatch, capsys
):
    # The outer main() boundary: a bug anywhere in _main() other than the
    # per-file scan loop (which isolates its own exceptions already) must
    # still come back as a clean exit 3, not a raw traceback with the
    # default exit code 1.
    def boom(paths):
        raise ValueError("simulated: bug outside the scan loop")

    monkeypatch.setattr(cli, "_expand_paths", boom)

    source = tmp_path / "x.sql"
    source.write_text("SELECT 1;\n", encoding="utf-8")

    exit_code = main([str(source)])
    captured = capsys.readouterr()
    assert exit_code == 3
    assert "ValueError" in captured.err
