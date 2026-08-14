import json
import re

from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.report_generator import to_json, to_markdown

SAMPLE_FINDING = Finding(
    detector="autonomous_tx",
    severity="high",
    object_name="LOGGER.PURGE_ALL",
    line=2178,
    snippet="pragma autonomous_transaction;",
    message="uses dblink | needs review",
)


def test_to_json_round_trips_finding_fields():
    parsed = json.loads(to_json([SAMPLE_FINDING]))
    assert parsed == [SAMPLE_FINDING.__dict__]


def test_to_markdown_empty_findings():
    assert "не найдено" in to_markdown([])


def test_to_markdown_renders_table_and_escapes_pipes():
    markdown = to_markdown([SAMPLE_FINDING])
    assert "LOGGER.PURGE_ALL" in markdown
    assert "2178" in markdown
    assert "high" in markdown
    assert "uses dblink \\| needs review" in markdown


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
        message="uses dblink",
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
