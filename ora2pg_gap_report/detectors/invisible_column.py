import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments, qualified_name_pattern, statement_end

_TABLE_RE = re.compile(
    qualified_name_pattern(r"CREATE\s+TABLE"),
    re.IGNORECASE,
)
# INVISIBLE is a column-definition trailing modifier in real Oracle DDL
# ('col_name datatype ... INVISIBLE'), always followed by a comma, the
# closing paren of the column list, or another trailing column/constraint
# clause -- never directly by a datatype keyword. That lookahead is what
# rules out the realistic collision: a column simply named "invisible"
# ('invisible NUMBER, ...'), where the next token is that column's own
# datatype, not one of these. INVISIBLE UNIQUE/PRIMARY KEY is Oracle's own
# documented example usage (hiding a unique/PK column), so the inline
# constraint keywords have to be in this list too, not just NOT/DEFAULT/
# ENCRYPT.
_INVISIBLE_RE = re.compile(
    r"\bINVISIBLE\b(?=\s*(?:,|\)|NOT\b|DEFAULT\b|ENCRYPT\b|UNIQUE\b|PRIMARY\b|"
    r"CONSTRAINT\b|REFERENCES\b|CHECK\b))",
    re.IGNORECASE,
)


def find_invisible_columns(source: str) -> list[Finding]:
    """Detect Oracle's INVISIBLE column modifier on CREATE TABLE. ora2pg
    drops it entirely, so the column becomes an ordinary visible one --
    not a syntax error, but a silent behavior change: SELECT * (and
    positional INSERT) on the converted table returns a column Oracle
    would have hidden. See docs/research/gap-020-invisible-column.md.

    object_name is the table's own name (schema-level DDL) -- same
    reasoning as table_partitioning.py/external_table.py for skipping
    enclosing_object_name(). Only CREATE TABLE is covered; ALTER TABLE ...
    MODIFY (col INVISIBLE) on an existing table is out of scope for now.

    Known residual false-positive: a column whose *datatype* (not name) is
    a user-defined type/domain literally called "invisible" and which is
    also the last column in the table ('tag invisible)') would be flagged
    -- the closing paren right after it looks identical to the real
    trailing-modifier position. Accepted as out of scope: a type actually
    named "invisible" is not a realistic naming choice in real schemas.

    Statement scoping uses statement_end() -- up to the next ';', or the
    start of the next CREATE TABLE if there's no ';' (DBMS_METADATA.GET_DDL's
    default output has none) -- not just "next ';' or end of file", which
    would otherwise misattribute a later table's own INVISIBLE columns to
    an earlier, unterminated one."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    table_matches = list(_TABLE_RE.finditer(clean))
    for i, m in enumerate(table_matches):
        next_start = table_matches[i + 1].start() if i + 1 < len(table_matches) else None
        stmt_end = statement_end(clean, m.end(), next_start)
        statement = clean[m.end() : stmt_end]
        table_name = m.group(1).upper()

        for im in _INVISIBLE_RE.finditer(statement):
            findings.append(
                Finding(
                    detector="invisible_column",
                    severity="high",
                    object_name=table_name,
                    line=line_at(clean, m.end() + im.start()),
                    snippet="INVISIBLE",
                    message_id="invisible_column",
                )
            )

    return findings
