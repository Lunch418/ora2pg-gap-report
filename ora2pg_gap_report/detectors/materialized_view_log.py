import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern

_MVIEW_LOG_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+MATERIALIZED\s+VIEW\s+LOG\s+ON"),
    re.IGNORECASE,
)


def find_materialized_view_logs(source: str) -> list[Finding]:
    """Detect Oracle's CREATE MATERIALIZED VIEW LOG ON <table>. ora2pg has
    no conversion path for these at all -- see
    docs/research/gap-027-materialized-view-log.md.

    object_name is the target table's name (schema-level DDL) -- same
    reasoning as table_partitioning.py/external_table.py for skipping
    enclosing_object_name()."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _MVIEW_LOG_RE.finditer(clean):
        findings.append(
            Finding(
                detector="materialized_view_log",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE MATERIALIZED VIEW LOG",
                message_id="materialized_view_log",
            )
        )

    return findings
