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
        message_id="read_only_table",
        source_file="foo.pkb",
    )
    defaults.update(kwargs)
    return Finding(**defaults)


def test_render_empty_findings_shows_a_positive_panel():
    console = Console(record=True, width=100)
    render([], console=console)
    text = console.export_text()
    assert "не найдено" in text


def test_render_explanation_panel_shows_gap_and_failure_stage():
    finding = _finding(detector="sequence_cycle", snippet="CYCLE")  # GAP-030, failure_stage="runtime"
    console = Console(record=True, width=100)
    render([finding], console=console)
    text = console.export_text()
    assert "GAP-030" in text
    assert "выполнение" in text


def test_render_explanation_panel_shows_gap_without_stage_for_an_exempt_gap():
    finding = _finding(detector="autonomous_tx")  # GAP-001, in FAILURE_STAGE_EXEMPT_DETECTORS
    console = Console(record=True, width=100)
    render([finding], console=console)
    text = console.export_text()
    assert "GAP-001" in text
    assert "Когда ломается" not in text


def test_render_explanation_panel_omits_gap_line_for_an_unregistered_detector():
    finding = _finding(detector="x")  # not a real detector/gap at all
    console = Console(record=True, width=100)
    render([finding], console=console)
    text = console.export_text()
    assert "GAP-" not in text


def test_render_shows_summary_counts_and_every_finding():
    findings = [
        _finding(severity="high", object_name="PKG.A"),
        _finding(severity="medium", object_name="PKG.B", snippet="s2", message_id="read_only_table"),
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()

    # Counted as what they are -- findings -- in the right grammatical form.
    assert "Найдено: 2 находки" in text
    assert "high" in text and "medium" in text
    assert "PKG.A" in text
    assert "PKG.B" in text
    assert "Оценка ручной доработки" in text


def test_render_handles_a_severity_outside_high_medium_low_without_crashing():
    findings = [_finding(severity="critical")]
    console = Console(record=True, width=200)
    render(findings, console=console)  # must not raise
    text = console.export_text()

    assert "other" in text  # effort_estimator's catch-all bucket
    assert "critical" in text  # still shown verbatim for the gap


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
            message_id="read_only_table",
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
    assert "Где больше всего находок" in text
    assert "PKG.A" in text
    assert "2 находки" in text


def test_render_skips_top_objects_tree_when_only_one_object():
    findings = [_finding(object_name="PKG.A"), _finding(object_name="PKG.A", snippet="s2")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    assert "Где больше всего находок" not in console.export_text()


def test_render_shows_elapsed_time_and_objects_scanned_when_provided():
    findings = [_finding()]
    console = Console(record=True, width=200)
    render(findings, console=console, elapsed_seconds=1.23, objects_scanned=7)
    text = console.export_text()
    assert "Просканировано: 7 объектов за 1.2 с." in text


def test_render_omits_elapsed_time_and_objects_scanned_when_not_provided():
    findings = [_finding()]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "Просканировано" not in text
    assert " за " not in text


def test_render_shows_the_effort_as_a_range_never_a_midpoint():
    # effort_estimator.py: "do not collapse it to an average and quote that
    # as a number; the spread itself is the honest part of the answer".
    # The old panel printed exactly that average ("Среднее 280 ч").
    findings = [_finding(severity="high")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text().lower()
    assert "2–8 ч" in text
    assert "неоткалиброванная эвристика" in text
    assert "среднее" not in text


def test_effort_panel_shows_patterns_note_when_a_detector_repeats():
    findings = [_finding(detector="autonomous_tx", object_name=f"PKG.F{i}") for i in range(3)]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "1 тип пробела на 3 находки" in text  # 1 distinct detector, not 3


def test_effort_panel_omits_patterns_note_when_every_finding_is_a_distinct_detector():
    findings = [
        _finding(detector="autonomous_tx", object_name="A"),
        _finding(detector="bulk_collect", object_name="B", snippet="s2", message_id="read_only_table"),
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "находок —" not in text


def test_top_objects_tree_truncates_beyond_the_limit_and_notes_the_remainder():
    findings = [_finding(object_name=f"PKG.OBJ{i}", snippet=f"s{i}") for i in range(15)]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "и ещё 5 объектов" in text


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


def test_render_shows_a_heading_and_the_remediation_with_a_known_detector():
    findings = [_finding(detector="autonomous_tx"), _finding(detector="autonomous_tx", snippet="s2")]
    console = Console(record=True, width=200)
    render(findings, console=console)
    text = console.export_text()
    assert "Oracle -> PostgreSQL" in text
    assert "Что делать" in text
    assert "autonomous_tx" in text
    assert "dblink" in text  # the real remediation hint for this detector, not a generic fallback


def test_gaps_are_listed_by_stage_then_by_finding_count():
    findings = [
        _finding(detector="goto_statement", object_name="A"),  # runtime, 1
        _finding(detector="bulk_collect", object_name="B", snippet="s2"),  # runtime, 3
        _finding(detector="bulk_collect", object_name="C", snippet="s3"),
        _finding(detector="bulk_collect", object_name="D", snippet="s4"),
        _finding(detector="authid_clause", object_name="E"),  # conversion, 1
    ]
    console = Console(record=True, width=200)
    render(findings, console=console)
    details = console.export_text().split("Подробно", 1)[1]
    assert details.index("authid_clause") < details.index("bulk_collect") < details.index("goto_statement")


def test_a_gap_lists_its_first_occurrences_and_points_at_the_full_list():
    findings = [_finding(detector="goto_statement", object_name=f"P{i}", line=i) for i in range(1, 9)]
    console = Console(record=True, width=200)
    render(findings, console=console)
    details = console.export_text().split("Подробно", 1)[1].split("Где больше всего находок", 1)[0]
    assert "P5" in details and "P6" not in details
    assert "и ещё 3 находки" in details
    assert "-f html -o report.html" in details


def test_every_detector_registered_in_cli_has_a_remediation_hint():
    # A detector added to core.py's scan loop without a corresponding
    # entry here would silently fall back to a generic "см. пояснение
    # ниже" line in the Рекомендации section instead of a real hint --
    # this test makes that an explicit failure instead of a silent gap.
    from ora2pg_gap_report import core
    from ora2pg_gap_report import messages

    for detector_fn in core._ORACLE_DETECTORS + core._MYSQL_DETECTORS:
        result = detector_fn("")  # empty source: no findings, just need the shape
        assert result == []
    # core.detector_names() derives each name from its function's own
    # __module__ -- the actual, current contents of every dialect's own
    # tuple, not a second hand-typed set that can silently drift from it
    # (a real regression this test previously had: its old hardcoded set
    # was 9 detectors behind core._DETECTORS by the time this was
    # caught). dialect=None pulls every registered detector across every
    # dialect -- see detector_names()'s own docstring.
    registered_names = set(core.detector_names(dialect=None)) | {
        "connect_by"
    }  # opt-in via --check-connect-by, not in any dialect's own tuple
    assert registered_names <= set(messages.REMEDIATION_HINTS)


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

    assert "Found: 1 finding, 1 kind of gap." in text
    assert "Найдено" not in text
    assert "where the migration breaks" in text
    assert "In detail" in text
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


def test_heading_mark_is_styled_on_its_own_not_the_whole_heading():
    """The accent belongs to the "* " mark only. Text("* ", style=...) set
    it as the base style of the whole line, and the heading came out all
    orange."""
    import io

    out = io.StringIO()
    console = Console(file=out, width=100, color_system="truecolor", force_terminal=True)
    render([_finding(detector="sequence_cycle", snippet="CYCLE")], console=console)
    heading = next(line for line in out.getvalue().splitlines() if "Oracle" in line)
    accent = "38;2;217;119;87"
    assert accent in heading.split("*", 1)[0]
    assert accent not in heading.split("Oracle", 1)[0].rsplit("\x1b[0m", 1)[-1]


def test_what_to_do_comes_before_why_in_a_gap_panel():
    console = Console(record=True, width=120)
    render([_finding(detector="sequence_cycle", snippet="CYCLE", message_id="sequence_cycle")], console=console)
    text = console.export_text()
    # The fix is what the reader acts on; the explanation follows it, the
    # same order as the TUI's detail box and the HTML report.
    assert text.index("Что делать") < text.index("после исчерпания диапазона")
