import io

from rich.console import Console

from ora2pg_gap_report.models import Finding
from ora2pg_gap_report.terminal_report import render


def _report(lang):
    finding = Finding(
        detector="bulk_collect",
        severity="high",
        object_name="PKG.P",
        line=3,
        snippet="BULK COLLECT INTO",
        message_id="bulk_collect.bulk_collect",
        source_file="pkg.sql",
    )
    buffer = io.StringIO()
    render([finding], console=Console(file=buffer, width=160), lang=lang)
    return buffer.getvalue()


def test_report_ends_with_the_next_commands_in_migration_order():
    text = _report("en")
    tail = text[text.index("Next"):]
    positions = [tail.index(c) for c in ("-f checklist -o MIGRATION.md", "--fix --write out/", "--load-check docker out/")]
    assert positions == sorted(positions)


def test_next_steps_are_translated():
    assert "Дальше" in _report("ru")


def test_gap_panel_links_its_recipe():
    text = _report("en")
    assert "Recipe: Collections and bulk operations" in text
    assert "docs/recipes/collections-and-bulk.md" in text
