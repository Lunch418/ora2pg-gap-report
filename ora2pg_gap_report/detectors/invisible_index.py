import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_INDEX_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+(?:UNIQUE\s+|BITMAP\s+)?INDEX"),
    re.IGNORECASE,
)
# Excludes two collision shapes where "invisible" is actually a column
# name being indexed, not the trailing INVISIBLE modifier: (1) unquoted,
# e.g. 'ON widgets(invisible, other_col)' -- always immediately followed
# by ',' or ')' there, never by the real modifier; (2) double-quoted,
# e.g. 'ON widgets("invisible")' -- mask_strings_and_comments() only masks
# single-quoted string literals/comments, never double-quoted identifiers,
# so the literal text survives with its quotes intact.
_INVISIBLE_RE = re.compile(r'(?<!")\bINVISIBLE\b(?!")(?!\s*[,)])', re.IGNORECASE)


def find_invisible_indexes(source: str) -> list[Finding]:
    """Detect Oracle's INVISIBLE index modifier. ora2pg drops it entirely,
    so the index becomes an ordinary visible one -- not a syntax error,
    but a silent behavior change: the optimizer starts considering an
    index Oracle would have hidden by default. See
    docs/research/gap-025-invisible-index.md.

    object_name is the index's own name (schema-level DDL) -- same
    reasoning as table_partitioning.py/external_table.py for skipping
    enclosing_object_name().

    Statement scoping uses statement_end() -- up to the next ';', or the
    start of the next CREATE INDEX if there's no ';' (DBMS_METADATA.GET_DDL's
    default output has none) -- not just "next ';' or end of file", which
    would otherwise misattribute a later index's own INVISIBLE modifier
    to an earlier, unterminated one. The reported line is the actual
    INVISIBLE token's line, not the statement's opening CREATE INDEX
    line -- real indexes are often multi-line, and pointing at the wrong
    line sends the reader to the wrong place in the file."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    index_matches = list(_INDEX_RE.finditer(clean))
    for i, m in enumerate(index_matches):
        next_start = index_matches[i + 1].start() if i + 1 < len(index_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]

        invisible_match = _INVISIBLE_RE.search(statement)
        if invisible_match is None:
            continue

        findings.append(
            Finding(
                detector="invisible_index",
                severity="medium",
                object_name=m.group(1).upper(),
                line=line_at(clean, m.end() + invisible_match.start()),
                snippet="INVISIBLE",
                message_id="invisible_index",
            )
        )

    return findings
