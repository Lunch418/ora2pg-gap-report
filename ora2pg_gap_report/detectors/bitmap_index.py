import re

from ..models import Finding
from ..plsql_lex import IDENTIFIER, line_at, mask_strings_and_comments

# CREATE [UNIQUE] BITMAP INDEX <name> -- captures the index's own name for
# attribution. BITMAP JOIN INDEX (a separate Oracle feature built on the
# same keyword) is matched too: it converts the same way and breaks the
# same way, and the alternative -- silently ignoring it -- would be the
# worse failure mode.
_BITMAP_INDEX_RE = re.compile(
    rf"\bCREATE\s+BITMAP\s+(?:JOIN\s+)?INDEX\s+({IDENTIFIER}(?:\s*\.\s*{IDENTIFIER})?)",
    re.IGNORECASE,
)


def find_bitmap_indexes(source: str) -> list[Finding]:
    """Detect Oracle's CREATE BITMAP INDEX. ora2pg rewrites it to a GIN
    index, which PostgreSQL refuses to create on an ordinary scalar
    column -- GIN has no default operator class for varchar or numeric --
    so the generated DDL fails at load time. See
    docs/research/gap-046-bitmap-index.md.

    object_name is the index's own name: this is standalone schema-level
    DDL, not a clause inside a CREATE TABLE, so there's no enclosing
    table to attribute it to (the target table is in the ON clause, but
    the failing object is the index itself)."""
    clean = mask_strings_and_comments(source)
    findings: list[Finding] = []

    for m in _BITMAP_INDEX_RE.finditer(clean):
        findings.append(
            Finding(
                detector="bitmap_index",
                severity="high",
                object_name=re.sub(r"\s+", "", m.group(1)).upper(),
                line=line_at(clean, m.start()),
                snippet="CREATE BITMAP INDEX",
                message_id="bitmap_index",
            )
        )

    return findings
