from ..models import Finding
from ..mysql_indexes import bare, index_clauses
from ..mysql_lex import line_at, mask_strings_and_comments


def find_mysql_index_prefix(source: str) -> list[Finding]:
    """Detect an index on a column prefix: `KEY idx (note(20))`, `UNIQUE KEY
    uq (code(8))` -- what MySQL requires for TEXT/BLOB columns and
    mysqldump writes as such.

    PostgreSQL has no prefix index, and ora2pg 25.0 (-m) mangles the
    clause: the INDEX spelling becomes `CREATE INDEX idx ON t (note"(20);`,
    an unterminated quoted identifier that swallows the rest of the file
    (psql reads nothing after it - --load-check skips the file); UNIQUE
    becomes `ADD UNIQUE ("note(20")`, a column that does not exist; KEY
    is GAP-073 on top. See docs/research/gap-127-mysql-index-prefix.md.

    One finding per index clause."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []
    for clause in index_clauses(source):
        if not clause.has_prefix:
            continue
        prefixed = ", ".join(f"{c}({n})" for c, n in clause.columns if n is not None)
        findings.append(
            Finding(
                detector="mysql_index_prefix",
                severity="high",
                object_name=clause.table,
                line=line_at(clean, clause.start),
                snippet=f"{bare(clause.name) if clause.name else clause.keyword} ({prefixed})",
                message_id="mysql_index_prefix",
            )
        )
    return findings
