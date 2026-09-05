import csv
import dataclasses
import io
import json
import re

from ora2pg_gap_report import messages
from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.report_generator import to_csv, to_html, to_json, to_markdown

SAMPLE_FINDING = Finding(
    detector="autonomous_tx",
    severity="high",
    object_name="LOGGER.PURGE_ALL",
    line=2178,
    snippet="pragma autonomous_transaction;",
    message_id="autonomous_tx",
)


def test_to_json_round_trips_finding_fields():
    parsed = json.loads(to_json([SAMPLE_FINDING]))["findings"]
    # autonomous_tx is GAP-001, one of the two gaps in
    # FAILURE_STAGE_EXEMPT_DETECTORS (see gap_registry.py) -- gap_number
    # is still populated, failure_stage stays null.
    assert parsed == [{**dataclasses.asdict(SAMPLE_FINDING), "gap_number": "001", "failure_stage": None}]


def test_to_json_includes_failure_stage_for_a_classified_gap():
    finding = Finding(
        detector="sequence_cycle",  # GAP-030, failure_stage="runtime"
        severity="high",
        object_name="SEQ",
        line=1,
        snippet="CYCLE",
        message_id="sequence_cycle",
    )
    parsed = json.loads(to_json([finding]))["findings"]
    assert parsed[0]["gap_number"] == "030"
    assert parsed[0]["failure_stage"] == "runtime"


def test_to_json_gap_number_and_failure_stage_are_null_for_an_unregistered_detector():
    finding = Finding(
        detector="dbms_utl_calls",  # a classifier, not a registered gap
        severity="low",
        object_name="X",
        line=1,
        snippet="x",
        message_id="dbms_utl_calls",
    )
    parsed = json.loads(to_json([finding]))["findings"]
    assert parsed[0]["gap_number"] is None
    assert parsed[0]["failure_stage"] is None


def test_to_markdown_empty_findings():
    assert "не найдено" in to_markdown([])


def test_to_markdown_renders_table_and_escapes_pipes():
    markdown = to_markdown([SAMPLE_FINDING])
    assert "LOGGER.PURGE_ALL" in markdown
    assert "2178" in markdown
    assert "high" in markdown
    # The message comes from the registry now, so a pipe can only reach a
    # cell through scanned content -- which is exactly where it has to be
    # escaped, or one Oracle identifier splits the row into two columns.
    piped = dataclasses.replace(SAMPLE_FINDING, object_name="A | B")
    assert "A \\| B" in to_markdown([piped])


def test_to_markdown_shows_gap_and_failure_stage():
    finding = Finding(
        detector="sequence_cycle",  # GAP-030, failure_stage="runtime"
        severity="high",
        object_name="SEQ",
        line=1,
        snippet="CYCLE",
        message_id="sequence_cycle",
    )
    markdown = to_markdown([finding])
    assert "GAP-030" in markdown
    assert "выполнение" in markdown


def test_to_markdown_shows_em_dash_for_an_unregistered_detector():
    finding = Finding(
        detector="dbms_utl_calls", severity="low", object_name="X", line=1, snippet="x", message_id="dbms_utl_calls"
    )
    markdown = to_markdown([finding])
    data_row = [line for line in markdown.splitlines() if line.startswith("|")][2]
    assert data_row.strip().endswith("| — | — |")


def test_to_markdown_escapes_pipe_in_source_file_and_object_name():
    # A scanned file path or a quoted Oracle identifier containing a
    # literal '|' (a valid Unix filename character, and Oracle quoted
    # identifiers accept nearly anything) used to break the generated
    # table's column count if left unescaped.
    finding = Finding(
        detector="autonomous_tx",
        severity="high",
        object_name='WEIRD|"OBJ"',
        line=1,
        snippet="pragma autonomous_transaction;",
        message_id="autonomous_tx",
        source_file="weird|file.sql",
    )
    markdown = to_markdown([finding])
    data_row = [line for line in markdown.splitlines() if line.startswith("| weird")][0]
    # An escaped '\|' is still a literal '|' character, so a raw count
    # doesn't distinguish "escaped" from "adds a column" — count only
    # unescaped pipes, which is what actually determines column count when
    # a Markdown table is parsed.
    unescaped_pipes = len(re.findall(r"(?<!\\)\|", data_row))
    header_pipes = len(re.findall(r"(?<!\\)\|", markdown.splitlines()[0]))
    assert unescaped_pipes == header_pipes
    assert "weird\\|file.sql" in markdown
    assert 'WEIRD\\|"OBJ"' in markdown


def test_to_csv_empty_findings_is_just_a_header_row():
    rows = list(csv.reader(io.StringIO(to_csv([]))))
    assert rows == [
        [
            "detector",
            "severity",
            "object_name",
            "line",
            "snippet",
            "message_id",
            "source_file",
            "message",
            "gap_number",
            "failure_stage",
        ]
    ]


def test_to_csv_round_trips_finding_fields():
    reader = csv.DictReader(io.StringIO(to_csv([SAMPLE_FINDING])))
    rows = list(reader)
    assert len(rows) == 1
    assert rows[0]["detector"] == "autonomous_tx"
    assert rows[0]["object_name"] == "LOGGER.PURGE_ALL"
    assert rows[0]["line"] == "2178"
    assert rows[0]["message_id"] == "autonomous_tx"
    # the prose is resolved beside the id, for whoever opens this in a
    # spreadsheet
    assert "dblink" in rows[0]["message"]
    assert rows[0]["gap_number"] == "001"
    assert rows[0]["failure_stage"] == ""


def test_to_csv_quotes_fields_containing_commas_and_newlines():
    finding = Finding(
        detector="autonomous_tx",
        severity="high",
        object_name="OBJ, WITH_COMMA",
        line=1,
        snippet="pragma autonomous_transaction;",
        message_id="autonomous_tx",
        source_file="a,b.sql",
    )
    csv_text = to_csv([finding])
    reader = csv.DictReader(io.StringIO(csv_text))
    row = next(reader)
    assert row["object_name"] == "OBJ, WITH_COMMA"
    assert row["source_file"] == "a,b.sql"
    # Newlines survive quoting too. They can't come from object_name or a
    # path, but the resolved message is a multi-sentence paragraph and is
    # written into the same row.
    assert row["message"] == messages.text("autonomous_tx")


def test_to_csv_uses_plain_newlines_not_crlf():
    # csv.writer's RFC-4180 default is '\r\n' -- explicitly overridden to
    # plain '\n' (see to_csv()'s docstring for why: avoids a '\r\r\n'
    # corruption when this string later goes through a text-mode file
    # write on Windows).
    csv_text = to_csv([SAMPLE_FINDING])
    assert "\r" not in csv_text


def test_to_csv_neutralizes_a_formula_injection_attempt_in_scanned_content():
    # snippet/object_name/source_file all come from scanned Oracle source,
    # not this codebase's own fixed strings -- a snippet or object name
    # starting with '=', '+', '-', '@', a tab, or a CR would open as a
    # live formula the instant the CSV is opened in Excel/Sheets/
    # LibreOffice. A leading "'" is the standard mitigation: every
    # affected app treats it as "this cell is literal text" and strips
    # the quote itself back out on display.
    finding = Finding(
        detector="autonomous_tx",
        severity="high",
        object_name="=cmd|' /C calc'!A1",
        line=1,
        snippet="+SUM(1,1)",
        message_id="autonomous_tx",
        source_file="@HYPERLINK(\"http://evil\")",
    )
    csv_text = to_csv([finding])
    assert "\n=cmd" not in csv_text
    assert "\n+SUM" not in csv_text
    assert "\n@HYPERLINK" not in csv_text
    reader = csv.DictReader(io.StringIO(csv_text))
    row = next(reader)
    assert row["object_name"] == "'=cmd|' /C calc'!A1"
    assert row["snippet"] == "'+SUM(1,1)"
    assert row["source_file"] == "'@HYPERLINK(\"http://evil\")"


def test_to_csv_does_not_touch_a_field_not_starting_with_a_formula_trigger():
    # A '=' or '+' appearing mid-field (not as the very first character)
    # never reaches a spreadsheet application's formula parser -- only a
    # leading trigger character needs neutralizing.
    csv_text = to_csv([SAMPLE_FINDING])
    reader = csv.DictReader(io.StringIO(csv_text))
    row = next(reader)
    assert row["object_name"] == "LOGGER.PURGE_ALL"
    assert not row["object_name"].startswith("'")


def test_to_html_empty_findings():
    report = to_html([])
    assert "не найдено" in report
    assert "<!doctype html>" in report.lower()


def test_to_html_renders_finding_fields():
    report = to_html([SAMPLE_FINDING])
    assert "LOGGER.PURGE_ALL" in report
    assert "2178" in report
    assert ">high<" in report
    assert "pragma autonomous_transaction;" in report


def test_to_html_shows_gap_and_failure_stage():
    finding = Finding(
        detector="sequence_cycle", severity="high", object_name="SEQ", line=1, snippet="CYCLE", message_id="sequence_cycle"
    )
    report = to_html([finding])
    assert "GAP-030" in report
    assert "выполнение" in report


def test_to_html_shows_em_dash_for_an_unregistered_detector():
    finding = Finding(
        detector="dbms_utl_calls", severity="low", object_name="X", line=1, snippet="x", message_id="dbms_utl_calls"
    )
    report = to_html([finding])
    assert '<td class="mono">—</td><td>—</td></tr>' in report


def test_to_html_shows_the_same_uncalibrated_effort_caveat_as_markdown():
    # Same discipline as effort_estimator.py/terminal_report.py: a range,
    # with the "not a measurement" caveat attached, never a bare number.
    report = to_html([SAMPLE_FINDING])
    assert "неоткалиброванная эвристика" in report


def test_to_html_escapes_finding_content_against_injection():
    # A scanned file path or an Oracle quoted identifier could contain
    # nearly any character (see test_to_markdown_escapes_pipe_in_source_
    # file_and_object_name for the same concern in the Markdown renderer)
    # -- unescaped, a '<'/'&' here would corrupt the HTML structure or, in
    # the worst case, be interpreted as a live tag by whatever opens the
    # report.
    finding = Finding(
        detector="autonomous_tx",
        severity="high",
        object_name='<script>alert(1)</script>',
        line=1,
        snippet="pragma autonomous_transaction;",
        message_id="autonomous_tx",
        source_file="<b>weird</b>.sql",
    )
    report = to_html([finding])
    assert "<script>alert(1)</script>" not in report
    assert "&lt;script&gt;" in report


def test_to_html_is_self_contained_with_no_external_resources():
    # This project's other formats are all designed to work in a closed
    # network (see README's "Установка без интернета" section) -- the
    # HTML report must not silently require internet access to render
    # correctly (an external stylesheet/font/script), unlike a typical
    # web-facing report template.
    report = to_html([SAMPLE_FINDING])
    assert "http://" not in report
    assert "https://" not in report
    assert "<link" not in report
    assert "<script" not in report


def test_to_html_severity_badge_classes():
    high = Finding(
        detector="autonomous_tx", severity="high", object_name="A", line=1,
        snippet="x", message_id="autonomous_tx",
    )
    medium = Finding(
        detector="autonomous_tx", severity="medium", object_name="B", line=1,
        snippet="x", message_id="autonomous_tx",
    )
    low = Finding(
        detector="autonomous_tx", severity="low", object_name="C", line=1,
        snippet="x", message_id="autonomous_tx",
    )
    report = to_html([high, medium, low])
    assert 'class="sev-high"' in report
    assert 'class="sev-medium"' in report
    assert 'class="sev-low"' in report


def test_to_markdown_empty_findings_in_english():
    assert "No problematic constructs found." in to_markdown([], lang="en")


def test_to_markdown_uses_english_column_headers():
    markdown = to_markdown([SAMPLE_FINDING], lang="en")
    assert "| File | Object | Line | Severity | Snippet | Problem | GAP | Fails at |" in markdown
    assert "Файл" not in markdown


def test_to_markdown_links_to_one_explanation_instead_of_inlining_it():
    # The explanation is 400-600 characters and identical for every
    # finding a detector produced. Inlined, a row ran to about a thousand
    # characters -- valid Markdown, unreadable as a table, and most of the
    # document's size.
    two = [SAMPLE_FINDING, dataclasses.replace(SAMPLE_FINDING, line=999)]
    markdown = to_markdown(two, lang="en")
    table_rows = [ln for ln in markdown.splitlines() if ln.startswith("| ") and "---" not in ln]
    assert all(len(row) < 200 for row in table_rows[1:]), table_rows[1:]

    explanation = messages.text(SAMPLE_FINDING.message_id, "en")
    assert markdown.count(explanation) == 1
    assert "## Explanations" in markdown
    assert f"### {SAMPLE_FINDING.detector}" in markdown


def test_the_markdown_link_target_matches_the_heading_anchor():
    # A link to an anchor that does not exist is worse than no link.
    markdown = to_markdown([SAMPLE_FINDING], lang="en")
    anchor = SAMPLE_FINDING.detector.replace("_", "")
    assert f"[{SAMPLE_FINDING.detector}](#{anchor})" in markdown
    # GitHub builds the anchor by lowercasing the heading and dropping
    # anything that isn't a word character or a space; a detector name is
    # already lowercase with underscores, so the two must agree.
    heading = f"### {SAMPLE_FINDING.detector}"
    assert heading in markdown
    assert "".join(c for c in heading[4:].lower() if c.isalnum()) == anchor


def test_to_markdown_writes_no_explanations_section_when_there_is_nothing_to_explain():
    assert "## Explanations" not in to_markdown([], lang="en")


def test_to_html_empty_findings_in_english():
    report = to_html([], lang="en")
    assert "No problematic constructs found." in report
    assert 'lang="en"' in report


def test_to_html_uses_english_headers_and_title():
    report = to_html([SAMPLE_FINDING], lang="en")
    assert "<th>File</th>" in report
    assert "ora2pg-gap-report report" in report
    assert "README.md" in report  # the effort-estimate caveat's citation, not PROJECT_BRIEF.md
    assert "PROJECT_BRIEF" not in report
