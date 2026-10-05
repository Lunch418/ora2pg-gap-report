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


def _report_for(detector, message_id, lang="en"):
    finding = Finding(
        detector=detector,
        severity="high",
        object_name="T_BI",
        line=1,
        snippet="DELIMITER //",
        message_id=message_id,
        source_file="dump.sql",
    )
    buffer = io.StringIO()
    render([finding], console=Console(file=buffer, width=160), lang=lang)
    return buffer.getvalue()


def test_prepare_comes_first_when_the_scan_found_something_it_removes():
    from ora2pg_gap_report import messages

    message_id = next(k for k in messages.MESSAGES if k.startswith("mysql_delimiter_trigger"))
    text = _report_for("mysql_delimiter_trigger", message_id)
    assert "Before ora2pg: ora2pg-gap-report --prepare --dialect mysql --write <dump>" in text
    tail = text[text.index("Next"):]
    assert tail.index("--prepare") < tail.index("-f checklist")


def test_no_prepare_step_when_nothing_needs_it():
    assert "--prepare" not in _report("en")


def test_next_commands_carry_a_non_oracle_dialect():
    from ora2pg_gap_report import messages

    message_id = next(k for k in messages.MESSAGES if k.startswith("mysql_delimiter_trigger"))
    tail = _report_for("mysql_delimiter_trigger", message_id).split("Next", 1)[1]
    assert "ora2pg-gap-report --dialect mysql --fix --write out/" in tail
    assert "ora2pg-gap-report --dialect mysql ... -f checklist" in tail
    assert "--dialect" not in _report("en").split("Next", 1)[1]
