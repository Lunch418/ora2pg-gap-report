import json

from src.models import Finding
from src.report_generator import to_json, to_markdown

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
