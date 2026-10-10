import re

from ..models import Finding
from ..plsql_lex import (
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
)

# A string literal, quotes doubled inside; read where only comments are masked.
_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")
# What makes an empty literal behave differently once Oracle's "'' is NULL"
# is gone -- the text right before it:
_CONTEXTS = (
    ("comparison", re.compile(r"(?:<>|!=|\^=|(?<![<>!:^])=)\s*\Z")),  # x = '', x <> ''
    ("assignment", re.compile(r":=\s*\Z")),  # v := ''
    ("default", re.compile(r"\bDEFAULT\s+\Z", re.IGNORECASE)),  # DEFAULT ''
    # NVL(x, ''), COALESCE(x, '')
    ("fallback", re.compile(r"\b(NVL|COALESCE)\s*\((?:[^()]|\([^()]*\))*,\s*\Z", re.IGNORECASE)),
)
_SNIPPET = {"comparison": "= ''", "assignment": ":= ''", "default": "DEFAULT ''"}
# The other side of a comparison: '' = x.
_COMPARED_AFTER_RE = re.compile(r"\s*(?:<>|!=|\^=|=)")


def find_empty_string_null(source: str) -> list[Finding]:
    """Detect an empty string literal where Oracle reads it as NULL: compared
    (`x = ''`, `x <> ''`), assigned (`v := ''`), a DEFAULT, or the fallback
    of NVL or COALESCE (`NVL(x, '')`).

    In Oracle '' is NULL; in PostgreSQL it is an ordinary, empty value.
    ora2pg 25.0 copies all of these as they are (its NULL_EQUAL_EMPTY option
    is off by default), and every one of them loads -- and then behaves
    differently, with no error: `x = ''` is never true in Oracle and true
    in PostgreSQL; `v := ''` makes `v IS NULL` true in Oracle, false in
    PostgreSQL; a column DEFAULT '' fills NULL in Oracle, '' in
    PostgreSQL; NVL(p, '') returns NULL in Oracle and, as coalesce(p, ''),
    '' in PostgreSQL (COALESCE(p, '') the same). Checked on a live Oracle
    23ai, ora2pg 25.0 and PostgreSQL 16. See
    docs/research/gap-129-empty-string-null.md.

    Concatenation ('a' || NULL is 'a' in Oracle, NULL in PostgreSQL) and
    LENGTH('') (NULL vs 0) are part of the same difference but are not
    flagged: they cannot be told from ordinary use by the text alone."""
    readable = mask_comments_only(source)
    if "''" not in readable:
        return []
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    findings: list[Finding] = []
    for literal in _LITERAL_RE.finditer(readable):
        if literal.group(0) != "''":
            continue
        before = clean[max(0, literal.start() - 200) : literal.start()]
        snippet = None
        for kind, context in _CONTEXTS:
            m = context.search(before)
            if m:
                snippet = f"{m.group(1).upper()}(..., '')" if kind == "fallback" else _SNIPPET[kind]
                break
        if snippet is None and _COMPARED_AFTER_RE.match(clean, literal.end()):
            snippet = "'' ="
        if snippet is None:
            continue
        findings.append(
            Finding(
                detector="empty_string_null",
                severity="high",
                object_name=enclosing_object_name(index, literal.start()),
                line=line_at(clean, literal.start()),
                snippet=snippet,
                message_id="empty_string_null",
            )
        )
    return findings
