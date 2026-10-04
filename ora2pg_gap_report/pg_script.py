"""Splits a PostgreSQL script into the statements psql would send, and
neutralises the few of them a --load-check must not run as written.

--load-check feeds ora2pg's generated files to a real psql inside one
transaction that is rolled back at the end (see load_check.py). Three
things in those files would defeat that, and ora2pg emits two of them in
the header of every file it writes:

- `\\set ON_ERROR_STOP ON` -- psql would stop at the first error, and the
  whole point is to see every statement that fails, not only the first.
- `SET check_function_bodies = false;` -- with it, PostgreSQL accepts any
  PL/pgSQL body without parsing it, so a procedure full of Oracle syntax
  "loads" cleanly. Every gap whose research doc says "PL/pgSQL fails at
  compile time" would be invisible.
- a top-level COMMIT / END / BEGIN / ROLLBACK -- would end the check's
  own transaction, and with it the guarantee that nothing is left behind
  in the target database.

They are blanked rather than removed: every character except line breaks
becomes a space, so line numbers -- and psql's error positions, which are
the whole output of a load check -- stay exactly those of the original
file.

The lexer mirrors psql's own rules for where a statement ends (psqlscan.l):
a semicolon outside quotes, dollar quotes, comments and parentheses. It is
not a SQL parser and does not try to be one; it only needs to agree with
psql on statement boundaries.
"""

from __future__ import annotations

import bisect
import dataclasses
import re

# A dollar-quote opener: `$$` or `$tag$`, where tag is an identifier that
# does not start with a digit (`$1` is a parameter, not a quote).
_DOLLAR_TAG_RE = re.compile(r"\$(?:[A-Za-z_\x80-\U0010ffff][A-Za-z0-9_\x80-\U0010ffff]*)?\$")
_WORD_RE = re.compile(r"[A-Za-z_]+")
_IDENT_CHAR_RE = re.compile(r"[A-Za-z0-9_\x80-\U0010ffff$]")

# Statements that control the transaction itself. Inside a load check
# they would commit or abandon the check's own transaction.
_TRANSACTION_CONTROL = frozenset(
    {"BEGIN", "START", "COMMIT", "END", "ROLLBACK", "ABORT", "SAVEPOINT", "RELEASE"}
)


@dataclasses.dataclass(frozen=True)
class Statement:
    """One statement as psql would send it.

    `start`/`end` are character offsets into the source (end exclusive,
    including the terminating semicolon when there is one). `start_line`
    is the line of the statement's first token -- leading blank lines and
    comments are not part of it, which is also what psql's `LINE n:`
    positions count from. `end_line` is the line psql reports an error
    on: the one holding the semicolon."""

    start: int
    end: int
    start_line: int
    end_line: int
    keywords: tuple[str, ...]  # up to the first three words, uppercased


@dataclasses.dataclass(frozen=True)
class MetaCommand:
    """A psql backslash command (`\\set ...`, `\\i file`, `\\connect`)."""

    start: int
    end: int
    line: int
    text: str


@dataclasses.dataclass(frozen=True)
class ParsedScript:
    statements: tuple[Statement, ...]
    meta_commands: tuple[MetaCommand, ...]
    # Set when the file ends inside a quote, a dollar quote or a block
    # comment: psql would carry the open text over into whatever it reads
    # next, so such a file cannot be loaded on its own.
    unterminated: str | None = None  # "quote" | "identifier" | "dollar_quote" | "comment"
    unterminated_line: int | None = None


@dataclasses.dataclass(frozen=True)
class Neutralised:
    """Something sanitize() blanked out, reported so the user knows what
    the check did not run."""

    line: int
    kind: str  # "meta" | "transaction" | "setting"
    text: str


class _LineIndex:
    def __init__(self, source: str) -> None:
        self._newlines = [i for i, ch in enumerate(source) if ch == "\n"]

    def line_of(self, offset: int) -> int:
        return bisect.bisect_left(self._newlines, offset) + 1


def _leading_keywords(text: str, limit: int = 3) -> tuple[str, ...]:
    words: list[str] = []
    pos = 0
    while len(words) < limit:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        m = _WORD_RE.match(text, pos)
        if m is None:
            break
        words.append(m.group(0).upper())
        pos = m.end()
    return tuple(words)


def parse_script(source: str) -> ParsedScript:
    """Statements and psql meta-commands of `source`, in order."""
    index = _LineIndex(source)
    statements: list[Statement] = []
    metas: list[MetaCommand] = []
    n = len(source)
    i = 0
    stmt_start: int | None = None
    depth = 0

    def close_statement(end: int) -> None:
        nonlocal stmt_start, depth
        if stmt_start is not None:
            text = source[stmt_start:end]
            statements.append(
                Statement(
                    start=stmt_start,
                    end=end,
                    start_line=index.line_of(stmt_start),
                    end_line=index.line_of(max(stmt_start, end - 1)),
                    keywords=_leading_keywords(text),
                )
            )
        stmt_start = None
        depth = 0

    def unterminated(kind: str, at: int) -> ParsedScript:
        return ParsedScript(tuple(statements), tuple(metas), kind, index.line_of(at))

    while i < n:
        ch = source[i]
        if ch.isspace():
            i += 1
            continue
        if source.startswith("--", i):
            nl = source.find("\n", i)
            i = n if nl == -1 else nl
            continue
        if source.startswith("/*", i):
            # PostgreSQL block comments nest.
            opened = i
            level = 1
            i += 2
            while i < n and level:
                if source.startswith("/*", i):
                    level += 1
                    i += 2
                elif source.startswith("*/", i):
                    level -= 1
                    i += 2
                else:
                    i += 1
            if level:
                return unterminated("comment", opened)
            continue
        if ch == "\\":
            # psql reads a backslash command up to the end of the line.
            # It does not end or join the statement being collected.
            nl = source.find("\n", i)
            end = n if nl == -1 else nl
            if end > i and source[end - 1] == "\r":
                end -= 1
            metas.append(MetaCommand(i, end, index.line_of(i), source[i:end].strip()))
            i = end
            continue

        if stmt_start is None:
            stmt_start = i

        if ch == "'":
            # E'...' takes backslash escapes; a plain literal does not
            # (standard_conforming_strings is on by default since 9.1).
            escapes = i > 0 and source[i - 1] in "eE" and (i < 2 or not _IDENT_CHAR_RE.match(source[i - 2]))
            opened = i
            i += 1
            while True:
                if i >= n:
                    return unterminated("quote", opened)
                c = source[i]
                if escapes and c == "\\":
                    i += 2
                    continue
                if c == "'":
                    if i + 1 < n and source[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == '"':
            opened = i
            i += 1
            while True:
                if i >= n:
                    return unterminated("identifier", opened)
                if source[i] == '"':
                    if i + 1 < n and source[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "$" and (i == 0 or not _IDENT_CHAR_RE.match(source[i - 1])):
            m = _DOLLAR_TAG_RE.match(source, i)
            if m is not None:
                tag = m.group(0)
                close = source.find(tag, m.end())
                if close == -1:
                    return unterminated("dollar_quote", i)
                i = close + len(tag)
                continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            close_statement(i + 1)
            i += 1
            continue
        i += 1

    # psql sends what is left in its buffer at the end of an \i'd file,
    # terminated or not -- so an unterminated last statement still runs.
    close_statement(n)
    return ParsedScript(tuple(statements), tuple(metas))


def _neutralisation(statement: Statement) -> str | None:
    words = statement.keywords
    if not words:
        return None
    first = words[0]
    if first in _TRANSACTION_CONTROL:
        # `START` is only a transaction statement as START TRANSACTION;
        # nothing else top-level begins with it, but be exact anyway.
        if first == "START" and words[1:2] != ("TRANSACTION",):
            return None
        return "transaction"
    if first == "PREPARE" and words[1:2] == ("TRANSACTION",):
        return "transaction"
    if first == "SET":
        rest = words[1:]
        if rest[:1] in (("SESSION",), ("LOCAL",)):
            rest = rest[1:]
        if rest[:1] == ("CHECK_FUNCTION_BODIES",):
            return "setting"
    return None


def _blank(chars: list[str], start: int, end: int) -> None:
    for k in range(start, end):
        if chars[k] not in "\r\n":
            chars[k] = " "


def _summary(text: str) -> str:
    one_line = " ".join(text.split())
    return one_line if len(one_line) <= 80 else one_line[:77] + "..."


def sanitize(source: str, parsed: ParsedScript | None = None) -> tuple[str, list[Neutralised]]:
    """`source` with psql meta-commands, transaction control and
    `SET check_function_bodies` blanked out (see the module docstring),
    plus what was blanked. Same length, same line breaks."""
    if parsed is None:
        parsed = parse_script(source)
    chars = list(source)
    removed: list[Neutralised] = []
    for meta in parsed.meta_commands:
        _blank(chars, meta.start, meta.end)
        removed.append(Neutralised(meta.line, "meta", _summary(meta.text)))
    for statement in parsed.statements:
        kind = _neutralisation(statement)
        if kind is not None:
            _blank(chars, statement.start, statement.end)
            removed.append(Neutralised(statement.start_line, kind, _summary(source[statement.start : statement.end])))
    removed.sort(key=lambda r: r.line)
    return "".join(chars), removed
