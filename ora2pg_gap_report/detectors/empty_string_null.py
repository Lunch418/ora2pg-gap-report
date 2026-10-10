import re

from ..models import Finding
from ..lex_common import table_column_definition_list
from ..plsql_lex import (
    IDENTIFIER,
    TABLE_HEAD,
    enclosing_object_name,
    enclosing_object_name_index,
    line_at,
    mask_comments_only,
    mask_strings_and_comments,
    qualified_name_pattern,
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
# What an assignment or a parameter's default sets: `v := ''`,
# `p VARCHAR2 DEFAULT ''`, `p IN VARCHAR2 := ''`.
_ASSIGNED_RE = re.compile(rf"({IDENTIFIER})(?:\s*\([^()]*\))?\s*:=\s*\Z")
_DEFAULTED_RE = re.compile(
    rf"({IDENTIFIER})\s+(?:IN\s+)?[A-Za-z0-9_$#.%]+(?:\s*\([^()]*\))?\s+(?:DEFAULT\s+|:=\s*)\Z", re.IGNORECASE
)
_TABLE_RE = re.compile(qualified_name_pattern(TABLE_HEAD), re.IGNORECASE)
# Words a statement can start after: `BEGIN v := ''` is an assignment to
# v, not a declaration of BEGIN.
_KEYWORDS = {"BEGIN", "THEN", "ELSE", "LOOP", "END", "IS", "AS", "DECLARE", "EXCEPTION", "ELSIF", "WHEN"}


def _null_test_re(name: str) -> re.Pattern[str]:
    """Where `name` is asked whether it is NULL: IS [NOT] NULL, NVL, NVL2,
    COALESCE, DECODE, LENGTH -- the uses whose answer changes when it
    holds '' instead of NULL."""
    n = re.escape(name)
    return re.compile(
        rf"(?<![\w$#.]){n}\s+IS\s+(?:NOT\s+)?NULL\b|\b(?:NVL2?|COALESCE|DECODE|LENGTH)\s*\(\s*{n}\s*[,)]",
        re.IGNORECASE,
    )


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
    flagged: they cannot be told from ordinary use by the text alone.

    An assignment or a parameter's default is flagged only where the same
    routine (or, for a package variable, the package) asks whether that
    name is NULL -- IS [NOT] NULL, NVL, COALESCE, DECODE, LENGTH: v := ''
    followed by v := v || x is the same in both. A column's DEFAULT '' is
    always flagged: its queries are elsewhere."""
    readable = mask_comments_only(source)
    if "''" not in readable:
        return []
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    tables = [span for m in _TABLE_RE.finditer(clean) if (span := table_column_definition_list(clean, m.end()))]

    def null_tested(name: str, obj: str) -> bool:
        """Whether `name` is tested for NULL in `obj`, or -- set at
        package level -- in any of the package's routines."""
        for m in _null_test_re(name).finditer(clean):
            where = enclosing_object_name(index, m.start())
            if where == obj or where.startswith(obj + "."):
                return True
        return False

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
        obj = enclosing_object_name(index, literal.start())
        if snippet in (":= ''", "DEFAULT ''") and not any(a < literal.start() < b for a, b in tables):
            # v := '' is NULL in Oracle and '' in PostgreSQL, and that only
            # shows where v is asked whether it is NULL: v := ''; v := v
            # || x is the same in both.
            declared = _DEFAULTED_RE.search(before)
            if declared is not None and declared.group(1).upper() not in _KEYWORDS:
                name = declared.group(1)  # v VARCHAR2(10) := '', p IN VARCHAR2 DEFAULT ''
            else:
                assigned = _ASSIGNED_RE.search(before)
                name = assigned.group(1) if assigned else None  # BEGIN v := ''
            if name is None or not null_tested(name, obj):
                continue
        findings.append(
            Finding(
                detector="empty_string_null",
                severity="high",
                object_name=obj,
                line=line_at(clean, literal.start()),
                snippet=snippet,
                message_id="empty_string_null",
            )
        )
    return findings
