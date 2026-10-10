"""--prepare: mechanical fixes to the *source* dump, before ora2pg reads it.

--fix repairs ora2pg's output after the fact. Some gaps cannot be repaired
there, because ora2pg has already thrown away what the fix would need: a
T-SQL script written with bracketed names comes out with types like
`[INT]` and the `nvarchar(100)` length gone (GAP-087); a MySQL routine
under `DELIMITER //` comes out with the delimiter inside its body
(GAP-106), a trigger under it not at all (GAP-107). Each of those
converts correctly when the same source is written in the plainer form
ora2pg's parser expects -- confirmed for every rewrite here by running
ora2pg 25.0 on both forms and loading the results into PostgreSQL 16.

So the rewrite goes on the input instead. The bar is the same as
autofix.py's: the source means exactly the same thing before and after,
in its own database. Removing brackets, a DELIMITER directive, a
version-comment wrapper or a DEFINER changes how the text is written, not
what it defines.

Every preparer works on the source dialect's own lexical rules (strings,
comments, quoted names), so nothing inside a literal or a comment is
touched.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator

Preparer = Callable[[str], tuple[str, int]]


# --- shared: walking code outside literals and comments ----------------------


def _mysql_segments(source: str) -> Iterator[tuple[int, int, str]]:
    """(start, end, kind) for every run of `source`, kind being "code",
    "string" (a '...' or "..." literal), "name" (a `backtick` name),
    "comment" or "versioned" (a /*!NNNNN ... */ comment, which MySQL runs
    as code). MySQL lexing: backslash escapes in strings, doubled quotes,
    `-- ` comments need the space, `#` comments run to the end of the
    line."""
    n = len(source)
    i = 0
    code_start = 0
    while i < n:
        ch = source[i]
        kind = None
        end = i
        if ch in "'\"":
            end = i + 1
            while end < n:
                if source[end] == "\\":
                    end += 2
                    continue
                if source[end] == ch:
                    if end + 1 < n and source[end + 1] == ch:
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            kind = "string"
        elif ch == "`":
            close = source.find("`", i + 1)
            end = n if close == -1 else close + 1
            kind = "name"
        elif ch == "#" or (source.startswith("--", i) and (i + 2 >= n or source[i + 2] in " \t\r\n")):
            nl = source.find("\n", i)
            end = n if nl == -1 else nl
            kind = "comment"
        elif source.startswith("/*", i):
            close = source.find("*/", i + 2)
            end = n if close == -1 else close + 2
            kind = "versioned" if source.startswith("/*!", i) else "comment"
        if kind is None:
            i += 1
            continue
        if code_start < i:
            yield code_start, i, "code"
        yield i, min(end, n), kind
        i = code_start = min(end, n)
    if code_start < n:
        yield code_start, n, "code"


def _masked(source: str, segments: Iterator[tuple[int, int, str]], hidden: frozenset[str]) -> str:
    """`source` with the segments of the `hidden` kinds blanked to spaces
    (line breaks kept), so a pattern can span names and code but never
    match inside a literal or a comment."""
    chars = list(source)
    for start, end, kind in segments:
        if kind in hidden:
            for k in range(start, end):
                if chars[k] not in "\r\n":
                    chars[k] = " "
    return "".join(chars)


def _sub_in_code(source: str, masked: str, pattern: re.Pattern[str], replacement: str) -> tuple[str, int]:
    """pattern.sub over `source`, matching against `masked`."""
    out: list[str] = []
    pos = 0
    count = 0
    for m in pattern.finditer(masked):
        out.append(source[pos : m.start()])
        out.append(m.expand(replacement) if "\\" in replacement else replacement)
        pos = m.end()
        count += 1
    out.append(source[pos:])
    return "".join(out), count


_MYSQL_HIDDEN = frozenset({"string", "comment", "versioned"})


# --- MySQL -------------------------------------------------------------------

_DELIMITER_LINE_RE = re.compile(r"^[ \t]*DELIMITER[ \t]+(\S+)[ \t]*\r?$", re.IGNORECASE | re.MULTILINE)


def prepare_mysql_delimiter(source: str) -> tuple[str, int]:
    """Drop mysql-client `DELIMITER x` directives and end each statement
    written under one with a plain `;` (GAP-106, GAP-107).

    `DELIMITER` is not SQL: the mysql client reads it to know where a
    statement ends, so a routine body can hold semicolons. ora2pg reads
    the file itself and does not interpret it -- the delimiter leaks into
    the routine's body, and a trigger under it is not generated at all.
    The same routine ended by `END;`, with no directive, converts
    correctly. Returns the number of directive blocks removed."""
    out: list[str] = []
    pos = 0
    blocks = 0
    delimiter = ";"
    matches = list(_DELIMITER_LINE_RE.finditer(source))
    # Only directives in code count; a DELIMITER inside a string or a
    # comment is text.
    code_spans = [(s, e) for s, e, kind in _mysql_segments(source) if kind == "code"]

    def in_code(at: int) -> bool:
        return any(s <= at < e for s, e in code_spans)

    for m in matches:
        if not in_code(m.start(1)):
            continue
        out.append(_replace_delimiter(source[pos : m.start()], delimiter))
        # drop the directive line together with its line break
        end = m.end()
        if source.startswith("\r\n", end):
            end += 2
        elif source.startswith("\n", end):
            end += 1
        pos = end
        delimiter = m.group(1)
        if delimiter != ";":
            blocks += 1
    out.append(_replace_delimiter(source[pos:], delimiter))
    return "".join(out), blocks


def _replace_delimiter(text: str, delimiter: str) -> str:
    if delimiter == ";":
        return text
    pieces: list[str] = []
    for start, end, kind in _mysql_segments(text):
        piece = text[start:end]
        if kind == "code":
            piece = piece.replace(delimiter, ";")
        pieces.append(piece)
    return "".join(pieces)


_DEFINER_RE = re.compile(
    r"\bDEFINER\s*=\s*(?:CURRENT_USER(?:\s*\(\s*\))?|(?:`[^`]*`|'[^']*'|\"[^\"]*\"|[\w.%-]+)\s*@\s*(?:`[^`]*`|'[^']*'|\"[^\"]*\"|[\w.%-]+))\s*",
    re.IGNORECASE,
)


def prepare_mysql_definer(source: str) -> tuple[str, int]:
    """Remove `DEFINER=user@host` from CREATE statements (GAP-108).

    The definer is the account a routine or view runs as in MySQL;
    PostgreSQL has no such clause (a routine runs as its caller unless it
    is SECURITY DEFINER, which `SQL SECURITY DEFINER` still says). With
    the clause in place ora2pg's -t PROCEDURE skips the procedure
    entirely; without it the procedure converts."""
    masked = _masked(source, _mysql_segments(source), _MYSQL_HIDDEN)
    return _sub_in_code(source, masked, _DEFINER_RE, "")


_VERSIONED_RE = re.compile(r"^/\*!\d{5}\s?(?P<body>.*?)\s*\*/$", re.DOTALL)
# What a mysqldump version comment wraps when it is part of an object's
# definition, as opposed to the session settings at the top of a dump
# (/*!40101 SET ... */), which are left as comments.
_DEFINITION_RE = re.compile(
    r"^\s*(?:CREATE|TRIGGER|VIEW|PROCEDURE|FUNCTION|EVENT|ALGORITHM|SQL\s+SECURITY|DEFINER)\b",
    re.IGNORECASE,
)


def prepare_mysql_versioned_comments(source: str) -> tuple[str, int]:
    """Unwrap the `/*!50003 ... */` comments mysqldump puts around triggers,
    views and routines, leaving their contents as plain SQL (GAP-109).

    MySQL runs the inside of a version comment as code; to anything else
    it is a comment, and ora2pg drops the object with it. Only comments
    whose contents are part of a definition (CREATE, TRIGGER, VIEW,
    ALGORITHM, DEFINER, SQL SECURITY, ...) are unwrapped: the session
    settings at the top of a dump stay comments."""
    segments = list(_mysql_segments(source))
    unwrapped: dict[int, str] = {}
    for index, (start, end, kind) in enumerate(segments):
        if kind == "versioned":
            m = _VERSIONED_RE.match(source[start:end])
            if m is not None and _DEFINITION_RE.match(m.group("body")):
                unwrapped[index] = m.group("body")
    out: list[str] = []
    for index, (start, end, kind) in enumerate(segments):
        piece = unwrapped.get(index, source[start:end])
        # mysqldump writes one definition as several comments on several
        # lines (CREATE ALGORITHM=... / DEFINER=... SQL SECURITY ... /
        # VIEW ...). Unwrapped, they are one statement; ora2pg's view parser
        # misses it when a line break follows SQL SECURITY, so the pieces
        # are joined on one line, which means the same thing.
        if (
            kind == "code"
            and not piece.strip()
            and index - 1 in unwrapped
            and index + 1 in unwrapped
        ):
            piece = " "
        out.append(piece)
    return "".join(out), len(unwrapped)


_IF_NOT_EXISTS_RE = re.compile(r"(\bCREATE\s+TABLE\s+)IF\s+NOT\s+EXISTS\s+", re.IGNORECASE)


def prepare_mysql_table_if_not_exists(source: str) -> tuple[str, int]:
    """`CREATE TABLE IF NOT EXISTS t` -> `CREATE TABLE t` (GAP-110).

    ora2pg reads `if` as the table's name. In a migration the target
    schema is new, so the clause never had a table to skip; without it
    the table converts under its own name."""
    masked = _masked(source, _mysql_segments(source), _MYSQL_HIDDEN)
    return _sub_in_code(source, masked, _IF_NOT_EXISTS_RE, r"\1")


# --- Oracle ------------------------------------------------------------------


def _oracle_segments(source: str) -> Iterator[tuple[int, int, str]]:
    """Like _mysql_segments for Oracle: '...' strings (doubled quotes),
    q'X...X' alternative-quoted strings (kind "qstring"), "..." names,
    -- and /* */ comments."""
    n = len(source)
    i = 0
    code_start = 0
    pairs = {"[": "]", "(": ")", "{": "}", "<": ">"}
    while i < n:
        ch = source[i]
        kind = None
        end = i
        is_q = (
            ch in "qQ"
            and source.startswith("'", i + 1)
            and i + 2 < n
            and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in "_$#"))
        ) or (
            ch in "nN"
            and i + 3 < n
            and source[i + 1] in "qQ"
            and source[i + 2] == "'"
            and (i == 0 or not (source[i - 1].isalnum() or source[i - 1] in "_$#"))
        )
        if is_q:
            quote = source.index("'", i)
            opener = source[quote + 1]
            closer = pairs.get(opener, opener)
            close = source.find(closer + "'", quote + 2)
            end = n if close == -1 else close + 2
            kind = "qstring"
        elif ch == "'":
            end = i + 1
            while end < n:
                if source[end] == "'":
                    if end + 1 < n and source[end + 1] == "'":
                        end += 2
                        continue
                    end += 1
                    break
                end += 1
            kind = "string"
        elif ch == '"':
            close = source.find('"', i + 1)
            end = n if close == -1 else close + 1
            kind = "name"
        elif source.startswith("--", i):
            nl = source.find("\n", i)
            end = n if nl == -1 else nl
            kind = "comment"
        elif source.startswith("/*", i):
            close = source.find("*/", i + 2)
            end = n if close == -1 else close + 2
            kind = "comment"
        if kind is None:
            i += 1
            continue
        if code_start < i:
            yield code_start, i, "code"
        yield i, min(end, n), kind
        i = code_start = min(end, n)
    if code_start < n:
        yield code_start, n, "code"


def prepare_oracle_alt_quote(source: str) -> tuple[str, int]:
    """`q'[it's]'` -> `'it''s'`: Oracle's alternative quoting rewritten as
    the ordinary literal it stands for (GAP-062).

    Both spell the same string in Oracle. ora2pg copies the q-form as it
    is, and PostgreSQL has no such syntax; the ordinary form converts
    like any other literal. `nq'...'` keeps its N prefix."""
    count = 0
    out: list[str] = []
    for start, end, kind in _oracle_segments(source):
        piece = source[start:end]
        if kind == "qstring" and piece.endswith("'"):
            prefix = "N" if piece[0] in "nN" else ""
            quote = piece.index("'")
            content = piece[quote + 2 : -2]
            piece = prefix + "'" + content.replace("'", "''") + "'"
            count += 1
        out.append(piece)
    return "".join(out), count


def prepare_oracle_table_if_not_exists(source: str) -> tuple[str, int]:
    """23ai's `CREATE TABLE IF NOT EXISTS t` -> `CREATE TABLE t` (GAP-112),
    for the same reason as MySQL's."""
    masked = _masked(source, _oracle_segments(source), frozenset({"string", "qstring", "comment"}))
    return _sub_in_code(source, masked, _IF_NOT_EXISTS_RE, r"\1")


_SEQUENCE_RE = re.compile(r"\bCREATE\s+SEQUENCE\s+((?:\"[^\"]+\"|[A-Za-z_][\w$#]*)(?:\s*\.\s*(?:\"[^\"]+\"|[A-Za-z_][\w$#]*))?)", re.IGNORECASE)
_SEQUENCE_END_RE = re.compile(r";|^\s*/\s*$", re.MULTILINE)
_START_WITH_RE = re.compile(r"\bSTART\s+WITH\b", re.IGNORECASE)
_INCREMENT_RE = re.compile(r"\bINCREMENT\s+BY\s+(-?)\s*\d", re.IGNORECASE)
_MINVALUE_RE = re.compile(r"\bMINVALUE\s+(-?\s*\d+)", re.IGNORECASE)
_MAXVALUE_RE = re.compile(r"\bMAXVALUE\s+(-?\s*\d+)", re.IGNORECASE)


def prepare_oracle_sequence_start(source: str) -> tuple[str, int]:
    """`CREATE SEQUENCE s CACHE 100` -> `CREATE SEQUENCE s START WITH 1
    CACHE 100`: the start Oracle implies -- MINVALUE (1 by default) going
    up, MAXVALUE (-1 by default) going down -- written out (GAP-143).

    ora2pg 25.0 writes an empty START for a sequence without one, which
    PostgreSQL does not parse, and cuts a trailing digit off a sequence
    name with no options at all."""
    masked = _masked(source, _oracle_segments(source), frozenset({"string", "qstring", "comment"}))
    inserts: list[tuple[int, str]] = []
    for m in _SEQUENCE_RE.finditer(masked):
        end = _SEQUENCE_END_RE.search(masked, m.end())
        options = masked[m.end() : end.start() if end else len(masked)]
        if _START_WITH_RE.search(options):
            continue
        down = (inc := _INCREMENT_RE.search(options)) is not None and inc.group(1) == "-"
        bound = (_MAXVALUE_RE if down else _MINVALUE_RE).search(options)
        start = "".join(bound.group(1).split()) if bound else ("-1" if down else "1")
        inserts.append((m.end(), f" START WITH {start}"))
    for at, text in reversed(inserts):
        source = source[:at] + text + source[at:]
    return source, len(inserts)


_ROUTINE_HEADER_RE = re.compile(
    r"\b(?:FUNCTION|PROCEDURE)\s+(?:[A-Za-z_][\w$#]*\s*\.\s*)?[A-Za-z_][\w$#]*\s*\(", re.IGNORECASE
)
_ASSIGN_RE = re.compile(r":=")


def prepare_oracle_param_default_spacing(source: str) -> tuple[str, int]:
    """`a varchar2:= chr(10)` -> `a varchar2 := chr(10)` in routine
    parameter lists (GAP-144): ora2pg 25.0 turns the := into DEFAULT
    without a space and glues it to its neighbours (`VARCHAR2DEFAULT`)."""
    from .lex_common import skip_balanced_parens

    masked = _masked(source, _oracle_segments(source), frozenset({"string", "qstring", "comment", "name"}))
    tight: list[int] = []
    for m in _ROUTINE_HEADER_RE.finditer(masked):
        close = skip_balanced_parens(masked, m.end() - 1)
        for a in _ASSIGN_RE.finditer(masked, m.end(), close):
            if not source[a.start() - 1].isspace() or not source[a.end()].isspace():
                tight.append(a.start())
    for at in reversed(tight):
        before = "" if source[at - 1].isspace() else " "
        after = "" if source[at + 2].isspace() else " "
        source = source[:at] + before + ":=" + after + source[at + 2 :]
    return source, len(tight)


# --- T-SQL -------------------------------------------------------------------

_PLAIN_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def prepare_mysql_indexes(source: str) -> tuple[str, int]:
    """mysqldump's index clauses, written the way ora2pg -m converts them
    (GAP-073, GAP-128):

    - `KEY idx (a)` -> `INDEX idx (a)`: the same index in MySQL; ora2pg
      turns the KEY spelling into a broken column, the INDEX one into a
      CREATE INDEX;
    - an unnamed `KEY (a)` / `INDEX (a)`, which ora2pg drops silently,
      gets the name `<table>_<first column>_idx`;
    - an index name used on more than one table -- fine in MySQL, where
      it belongs to the table, a clash in PostgreSQL, where it belongs to
      the schema -- becomes `<table>_<name>`.

    UNIQUE, FULLTEXT and SPATIAL keys are left alone (ora2pg converts the
    first, the others are gaps of their own), and so is an index on a
    column prefix, `KEY idx (note(20))` (GAP-127): PostgreSQL has no prefix
    index, and what to write instead is not a mechanical choice."""
    from .mysql_indexes import bare, colliding_names, index_clauses

    clauses = index_clauses(source)
    clashes = colliding_names(clauses)
    count = 0
    for clause in reversed(clauses):
        if clause.qualifier is not None or clause.has_prefix:
            continue
        name_end = clause.name_start + len(clause.name or "")
        if clause.name is None:
            new_name = f"`{clause.table}_{clause.columns[0][0]}_idx`"
            source = source[: clause.name_start] + " " + new_name + source[clause.name_start :]
        elif bare(clause.name).lower() in clashes:
            new_name = f"`{clause.table}_{bare(clause.name)}`"
            source = source[: clause.name_start] + new_name + source[name_end:]
        elif clause.keyword.upper() == "INDEX":
            continue
        if clause.keyword.upper() == "KEY":
            at = clause.keyword_start
            source = source[:at] + "INDEX" + source[at + len(clause.keyword) :]
        count += 1
    return source, count


def prepare_mssql_brackets(source: str) -> tuple[str, int]:
    """`[dbo].[Orders]` -> `dbo.Orders`, `[nvarchar](100)` -> `nvarchar(100)`
    (GAP-087).

    In T-SQL brackets only quote a name. ora2pg keeps them as part of the
    name, quotes that, and loses the types they wrap: the table comes out
    as "[dbo]"."[orders]" with columns of type [INT]. Written without the
    brackets, the same script converts correctly. A bracketed name that is
    a plain identifier loses its brackets; one that needs quoting (a space,
    a dash) becomes a double-quoted name, T-SQL's other spelling of the
    same thing. Strings and comments are left alone."""
    count = 0
    out: list[str] = []
    n = len(source)
    i = 0
    while i < n:
        ch = source[i]
        if ch == "'" or (ch in "nN" and source.startswith("'", i + 1)):
            start = i
            i = source.index("'", i) + 1
            while i < n:
                if source[i] == "'":
                    if i + 1 < n and source[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            out.append(source[start:i])
        elif source.startswith("--", i):
            nl = source.find("\n", i)
            end = n if nl == -1 else nl
            out.append(source[i:end])
            i = end
        elif source.startswith("/*", i):
            close = source.find("*/", i + 2)
            end = n if close == -1 else close + 2
            out.append(source[i:end])
            i = end
        elif ch == '"':
            close = source.find('"', i + 1)
            end = n if close == -1 else close + 1
            out.append(source[i:end])
            i = end
        elif ch == "[":
            # ]] inside brackets is an escaped ]
            j = i + 1
            name: list[str] = []
            while j < n:
                if source[j] == "]":
                    if source.startswith("]]", j):
                        name.append("]")
                        j += 2
                        continue
                    break
                if source[j] == "\n":
                    break
                name.append(source[j])
                j += 1
            if j < n and source[j] == "]" and name:
                text = "".join(name)
                out.append(text if _PLAIN_NAME_RE.match(text) else '"' + text.replace('"', '""') + '"')
                count += 1
                i = j + 1
            else:
                out.append(ch)
                i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out), count


_GO_LINE_RE = re.compile(r"^[ \t]*GO(?:[ \t]+\d+)?[ \t]*;?[ \t]*(?:\r?\n|\Z)", re.IGNORECASE | re.MULTILINE)
_TABLE_LINE_RE = re.compile(r"^CREATE\s+TABLE\b", re.IGNORECASE | re.MULTILINE)


def prepare_mssql_go_separator(source: str) -> tuple[str, int]:
    """Drop the `GO` lines SSMS writes after every object, and end each
    batch's last statement with `;` (GAP-126, GAP-149).

    ora2pg -M reads a routine up to the next CREATE, so the `GO` after it
    ends up inside the PL/pgSQL body (`END GO END;`) and the routine does
    not load. Without the GO, a routine whose last line is a bare `END`
    loses its closing END instead; with `END;` it converts and loads.
    Any other statement without its `;` -- CREATE TABLE ... ) GO, the way
    SSMS writes them -- makes ora2pg drop everything after it up to the
    next `;`: in Sakila, 15 of 16 tables. GO is a client-side batch
    separator, not SQL, and ora2pg splits objects on CREATE anyway, so
    nothing is lost. Strings and comments are left alone."""
    from .mssql_lex import mask_strings_and_comments

    masked = mask_strings_and_comments(source)
    # A CREATE TABLE at the start of a line after a statement with neither
    # ; nor GO ends that statement too (Sakila's film_text).
    tables = [t.start() for t in _TABLE_LINE_RE.finditer(masked)]
    for at in reversed(tables):
        before = masked[:at].rstrip()
        if before and not before.endswith(";") and not _GO_LINE_RE.search(before[before.rfind("\n") + 1 :] + "\n"):
            end = len(before)
            source = source[:end] + ";" + source[end:]
            masked = masked[:end] + ";" + masked[end:]
    gos = list(_GO_LINE_RE.finditer(masked))
    for go in reversed(gos):
        source = source[: go.start()] + source[go.end() :]
        masked = masked[: go.start()] + masked[go.end() :]
        before = masked[: go.start()].rstrip()
        if before and not before.endswith(";"):
            at = len(before)
            source = source[:at] + ";" + source[at:]
            masked = masked[:at] + ";" + masked[at:]
    return source, len(gos)


def prepare_mssql_index_names(source: str) -> tuple[str, int]:
    """An index name used on a second table -> `<table>_<name>` (GAP-150):
    in PostgreSQL an index name belongs to the schema, so ora2pg's second
    CREATE INDEX with the same name fails. The first table keeps it."""
    from .detectors.mssql_index_name_collision import index_statements, table_of
    from .mssql_lex import mask_strings_and_comments, normalize_name

    masked = mask_strings_and_comments(source)
    owner: dict[str, str] = {}
    renames: list[tuple[int, int, str]] = []
    for m in index_statements(masked):
        name = normalize_name(m.group(1))
        table = table_of(m)
        if owner.setdefault(name.lower(), table) == table:
            continue
        new = f"{table}_{name}"
        renames.append((m.start(1), m.end(1), f"[{new}]" if m.group(1).startswith("[") else new))
    for start, end, new in reversed(renames):
        source = source[:start] + new + source[end:]
    return source, len(renames)


# Which preparers run for which source dialect, in order. The delimiter
# comes first: the definer and version-comment rewrites must see the
# statements as plain SQL.
PREPARERS_BY_DIALECT: dict[str, tuple[Preparer, ...]] = {
    "oracle": (
        prepare_oracle_alt_quote,
        prepare_oracle_table_if_not_exists,
        prepare_oracle_sequence_start,
        prepare_oracle_param_default_spacing,
    ),
    "mysql": (
        prepare_mysql_versioned_comments,
        prepare_mysql_delimiter,
        prepare_mysql_definer,
        prepare_mysql_table_if_not_exists,
        prepare_mysql_indexes,
    ),
    "mssql": (prepare_mssql_index_names, prepare_mssql_brackets, prepare_mssql_go_separator),
}

def prepare_command(detector: str) -> str | None:
    """The --prepare command that removes this detector's gap before ora2pg
    runs, or None if no preparer covers it."""
    for dialect, preparers in PREPARERS_BY_DIALECT.items():
        for preparer in preparers:
            if detector in PREPARED_DETECTORS.get(preparer, ()):
                flag = "" if dialect == "oracle" else f" --dialect {dialect}"
                return f"ora2pg-gap-report --prepare{flag} --write <dump>"
    return None


# The detector whose gap each preparer removes the cause of.
PREPARER_DETECTOR: dict[Preparer, str] = {
    prepare_oracle_alt_quote: "alt_quote_literal",
    prepare_oracle_table_if_not_exists: "table_if_not_exists",
    prepare_oracle_sequence_start: "sequence_without_start",
    prepare_oracle_param_default_spacing: "param_default_spacing",
    prepare_mysql_versioned_comments: "mysql_versioned_comment",
    prepare_mysql_delimiter: "mysql_delimiter_routine",
    prepare_mysql_definer: "mysql_definer_procedure",
    prepare_mysql_table_if_not_exists: "mysql_create_table_if_not_exists",
    prepare_mssql_brackets: "mssql_bracket_identifier",
    prepare_mysql_indexes: "mysql_key_index",
    prepare_mssql_go_separator: "mssql_go_separator",
    prepare_mssql_index_names: "mssql_index_name_collision",
}

# Every detector whose gap a preparer removes. The DELIMITER rewrite covers
# two: a routine (GAP-106) and a trigger (GAP-107) under the directive.
PREPARED_DETECTORS: dict[Preparer, tuple[str, ...]] = {
    preparer: (detector,) for preparer, detector in PREPARER_DETECTOR.items()
}
PREPARED_DETECTORS[prepare_mysql_delimiter] = ("mysql_delimiter_routine", "mysql_delimiter_trigger")
PREPARED_DETECTORS[prepare_mysql_indexes] = ("mysql_key_index", "mysql_index_name_collision")
PREPARED_DETECTORS[prepare_mssql_go_separator] = ("mssql_go_separator", "mssql_statement_terminator")
