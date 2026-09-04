import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_GTT_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+GLOBAL\s+TEMPORARY\s+TABLE"),
    re.IGNORECASE,
)
_PRESERVE_ROWS_RE = re.compile(r"\bON\s+COMMIT\s+PRESERVE\s+ROWS\b", re.IGNORECASE)


def find_global_temp_tables_without_delete_rows(source: str) -> list[Finding]:
    """Detect Oracle GLOBAL TEMPORARY TABLE declarations that need
    Oracle's default/explicit ON COMMIT DELETE ROWS semantics but whose
    ora2pg conversion silently drops the ON COMMIT clause entirely,
    landing on PostgreSQL's opposite default (PRESERVE ROWS) -- a silent
    semantic change, not a syntax error, confirmed to actually happen at
    runtime (a row really does survive a COMMIT that should have cleared
    it). See docs/research/gap-012-global-temp-table.md.

    A table explicitly declared 'ON COMMIT PRESERVE ROWS' is not flagged
    -- that case matches PostgreSQL's own default and converts correctly
    (also confirmed empirically).

    Statement scoping uses statement_end() -- up to the next ';', or the
    start of the next CREATE GLOBAL TEMPORARY TABLE if there's no ';'
    (DBMS_METADATA.GET_DDL's default output has none) -- not just "next
    ';' or end of file", which would otherwise let an unrelated later
    table's own PRESERVE ROWS clause bleed into an earlier, unterminated
    one and wrongly suppress its finding."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    gtt_matches = list(_GTT_RE.finditer(clean))
    for i, m in enumerate(gtt_matches):
        next_start = gtt_matches[i + 1].start() if i + 1 < len(gtt_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        if _PRESERVE_ROWS_RE.search(statement):
            continue

        findings.append(
            Finding(
                detector="global_temp_table",
                severity="high",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE GLOBAL TEMPORARY TABLE",
                message_id="global_temp_table",
            )
        )

    return findings
