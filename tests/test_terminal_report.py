from rich.console import Console

from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.terminal_report import render


def _finding(**kwargs):
    defaults = dict(
        detector="x",
        severity="high",
        object_name="PKG.FOO",
        line=10,
        snippet="pragma autonomous_transaction;",
        message="explanation text",
        source_file="foo.pkb",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def test_render_empty_findings_shows_a_positive_panel():
    console = Console(record=True, width=100)
    render([], console=console)
    text = console.export_text()
    assert "не найдено" in text


def test_render_shows_summary_counts_and_every_finding():
    findings = [
        _finding(severity="high", object_name="PKG.A"),
        _finding(severity="medium", object_name="PKG.B", snippet="s2", message="m2"),
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()

    assert "Найдено проблемных объектов" in text and "2" in text
    assert "HIGH" in text and "MEDIUM" in text
    assert "PKG.A" in text
    assert "PKG.B" in text
    assert "Оценка ручной доработки" in text


def test_render_handles_a_severity_outside_high_medium_low_without_crashing():
    findings = [_finding(severity="critical")]
    console = Console(record=True, width=200)
    render(findings, console=console)  # must not raise
    text = console.export_text()

    assert "OTHER" in text  # effort_estimator's catch-all bucket
    assert "critical" in text  # still shown verbatim in the per-row column


def test_render_shows_source_file_column():
    findings = [_finding(source_file="docs/samples/logger.pkb")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    assert "logger.pkb" in console.export_text()


def test_render_does_not_crash_on_bracket_content_in_finding_fields():
    # Finding content comes straight from the Oracle files being scanned —
    # arbitrary text, not our own trusted markup. A file path/snippet
    # containing brackets used to raise rich.errors.MarkupError (mismatched
    # closing tag) because add_row() received plain strings, which Rich
    # parses as its own markup language by default.
    findings = [
        _finding(
            source_file="notes[/archive].sql",
            object_name="PKG.ARR[I][J]",
            snippet="arr[i][j] := 1;",
            message="see arr[i] for details",
        )
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)  # must not raise MarkupError
    text = console.export_text()

    # and the content must survive verbatim, not be silently swallowed as
    # if it were a (mismatched or valid-looking) style tag
    assert "notes[/archive].sql" in text
    assert "PKG.ARR[I][J]" in text
    assert "arr[i][j] := 1;" in text


def test_render_does_not_strip_content_that_looks_like_a_valid_style_tag():
    # A snippet containing something that happens to match a real Rich
    # style name (e.g. "[red]") must render literally, not be interpreted
    # and stripped as coloured markup.
    findings = [_finding(snippet="v_colors[red] := 1;")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    assert "v_colors[red] := 1;" in console.export_text()


def test_render_shows_top_objects_tree_when_multiple_objects_present():
    findings = [
        _finding(object_name="PKG.A", severity="high"),
        _finding(object_name="PKG.A", severity="medium", snippet="s2"),
        _finding(object_name="PKG.B", severity="low", snippet="s3"),
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "Объекты с наибольшим числом находок" in text
    assert "PKG.A" in text
    assert "2 находок" in text


def test_render_skips_top_objects_tree_when_only_one_object():
    findings = [_finding(object_name="PKG.A"), _finding(object_name="PKG.A", snippet="s2")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    assert "Объекты с наибольшим числом находок" not in console.export_text()


def test_render_shows_elapsed_time_and_objects_scanned_when_provided():
    findings = [_finding()]
    console = Console(record=True, width=200)
    render(findings, console=console, elapsed_seconds=1.23, objects_scanned=7)
    text = console.export_text()
    assert "Время анализа" in text and "1.2 с" in text
    assert "Объектов просканировано" in text and "7" in text


def test_render_omits_elapsed_time_and_objects_scanned_when_not_provided():
    findings = [_finding()]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "Время анализа" not in text
    assert "Объектов просканировано" not in text


def test_render_shows_best_expected_worst_case_effort():
    findings = [_finding(severity="high")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text().lower()
    assert "лучший случай" in text
    assert "среднее" in text
    assert "худший случай" in text


def test_top_objects_tree_truncates_beyond_the_limit_and_notes_the_remainder():
    findings = [_finding(object_name=f"PKG.OBJ{i}", snippet=f"s{i}") for i in range(15)]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "и ещё 5 объект(ов)" in text


def test_render_shows_stats_even_when_filters_leave_no_findings():
    # objects_scanned/elapsed_seconds are computed before any --severity/
    # --object filtering happens in cli.py -- if the filters legitimately
    # exclude every finding, render() used to hit the empty-findings early
    # return before ever looking at those parameters, silently dropping
    # them from the output.
    console = Console(record=True, width=200)
    render([], console=console, elapsed_seconds=2.5, objects_scanned=3)
    text = console.export_text()
    assert "Объектов просканировано: 3" in text
    assert "Время анализа: 2.5 с" in text


def test_render_shows_a_banner_and_recommendations_with_a_known_detector():
    findings = [_finding(detector="autonomous_tx"), _finding(detector="autonomous_tx", snippet="s2")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "ORACLE" in text and "POSTGRESQL" in text
    assert "Рекомендации" in text
    assert "autonomous_tx" in text
    assert "dblink" in text  # the real remediation hint for this detector, not a generic fallback


def test_recommended_actions_orders_detectors_by_finding_count_descending():
    findings = [
        _finding(detector="dbms_utl_calls", object_name="A"),
        _finding(detector="bulk_collect", object_name="B", snippet="s2"),
        _finding(detector="bulk_collect", object_name="C", snippet="s3"),
        _finding(detector="bulk_collect", object_name="D", snippet="s4"),
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    # Slice to the "Рекомендации" panel specifically -- both detector names
    # also appear earlier, in the "top objects" tree, whose own ordering
    # (by per-object count, not per-detector total) isn't what this test
    # is about.
    recommendations = console.export_text().split("Рекомендации", 1)[1]
    assert recommendations.index("bulk_collect") < recommendations.index("dbms_utl_calls")


def test_every_detector_registered_in_cli_has_a_remediation_hint():
    # A detector added to cli.py without a corresponding entry here would
    # silently fall back to a generic "см. пояснение ниже" line in the
    # Рекомендации section instead of a real hint — this test makes that
    # an explicit failure instead of a silent gap.
    from ora2pg_gap_report import cli
    from ora2pg_gap_report.terminal_report import _REMEDIATION_HINT

    registered_names = set()
    for detector_fn in cli._DETECTORS:
        result = detector_fn("")  # empty source: no findings, just need the shape
        assert result == []
    # detector names aren't derivable from the function alone without
    # calling it on real content; assert against the known, current set
    # instead (keeps this test meaningful without over-engineering a
    # generic detector-name registry that doesn't otherwise exist).
    registered_names = {
        "autonomous_tx",
        "compound_triggers",
        "dbms_utl_calls",
        "merge_delete_clause",
        "bulk_collect",
        "database_link",
        "model_clause",
        "pivot_clause",
        "object_type",
        "with_function",
        "flashback_query",
        "global_temp_table",
        "table_partitioning",
        "connect_by_nocycle",
        "context_object",
        "insert_all",
        "json_table",
        "external_table",
        "sql_macro",
        "invisible_column",
        "collection_type",
        "cross_apply",
        "oracle_text",
        "recursive_with",
        "invisible_index",
        "read_only_table",
        "materialized_view_log",
        "identity_column",
        "connect_by",  # opt-in via --check-connect-by, not in cli._DETECTORS
    }
    assert registered_names <= set(_REMEDIATION_HINT.keys())


def test_render_empty_findings_in_english():
    console = Console(record=True, width=100)
    render([], console=console, lang="en")
    text = console.export_text()
    assert "No problematic constructs found." in text


def test_render_uses_english_ui_strings_and_hint_when_lang_is_en():
    findings = [_finding(detector="read_only_table")]
    console = Console(record=True, width=200)
    render(findings, console=console, lang="en")
    text = console.export_text()

    assert "Problematic objects found" in text
    assert "Найдено" not in text
    assert "All findings" in text
    assert "Recommendations" in text
    assert "Explanations" in text
    assert "Manual rework estimate" in text
    # the English remediation hint for read_only_table, not the Russian one
    assert "ora2pg drops the READ ONLY section" in text


def test_render_baseline_diff_in_english():
    from ora2pg_gap_report.baseline import BaselineDiff
    from ora2pg_gap_report.terminal_report import render_baseline_diff

    diff = BaselineDiff(new=[_finding()], resolved=[], unchanged_count=0)
    console = Console(record=True, width=200)
    render_baseline_diff(diff, console=console, lang="en")
    text = console.export_text()
    assert "Baseline comparison" in text
    assert "New findings" in text


def test_render_verification_shows_counts_and_status_per_detector():
    from ora2pg_gap_report.terminal_report import render_verification
    from ora2pg_gap_report.verification import DetectorVerification

    results = [
        DetectorVerification("cross_apply", "022", 3, 1, "still_present"),
        DetectorVerification("json_table", "017", 2, 0, "not_detected"),
        DetectorVerification("read_only_table", "026", 1, 0, "not_verifiable"),
    ]
    console = Console(record=True, width=140)
    render_verification(results, console=console)
    text = console.export_text()

    assert "STILL_PRESENT" in text
    assert "NOT_DETECTED" in text
    assert "NOT_VERIFIABLE" in text
    assert "cross_apply" in text
    assert "GAP-022" in text
    # not_verifiable's post-migration count is deliberately hidden (—),
    # not printed as a misleading 0
    assert "read_only_table" in text


def test_render_verification_with_no_registered_gap_shows_a_placeholder():
    from ora2pg_gap_report.terminal_report import render_verification
    from ora2pg_gap_report.verification import DetectorVerification

    results = [DetectorVerification("dbms_utl_calls", None, 1, 1, "still_present")]
    console = Console(record=True, width=140)
    render_verification(results, console=console)
    text = console.export_text()
    assert "dbms_utl_calls" in text
    assert "GAP-None" not in text


def test_render_verification_empty_results():
    from ora2pg_gap_report.terminal_report import render_verification

    console = Console(record=True, width=140)
    render_verification([], console=console)
    text = console.export_text()
    assert "0" in text


def test_render_verification_in_english():
    from ora2pg_gap_report.terminal_report import render_verification
    from ora2pg_gap_report.verification import DetectorVerification

    results = [DetectorVerification("cross_apply", "022", 1, 1, "still_present")]
    console = Console(record=True, width=140)
    render_verification(results, console=console, lang="en")
    text = console.export_text()
    assert "Post-migration verification" in text
    assert "Still present" in text
    assert "Проверка после миграции" not in text
