"""Repairs to ora2pg's output that need the source it was made from.

--fix can only repair what the generated file itself shows to be wrong
and how to put right. Some gaps lose the answer in conversion: which
triggers were statement-level (GAP-118), what a package constant's value
is (GAP-114, GAP-119, and every constant read GAP-036 breaks), which values
a MySQL ENUM had (GAP-068). --migrate has both the source and the output,
so it can put them back. Each repair restores exactly what the source
says, nothing chosen:

- a trigger the source declares without FOR EACH ROW becomes FOR EACH
  STATEMENT again, and its function returns NULL (a statement trigger has
  no row to return);
- a package CONSTANT whose value is a literal, or a concatenation of
  literals and earlier constants, is written as that literal wherever
  ora2pg left a reference to it: a current_setting() read (which nothing
  ever set_config()s), the spliced expression of GAP-114, a parameter
  DEFAULT (GAP-119). Variables are left alone -- their value changes;
- the CREATE TYPE ... AS ENUM ora2pg names but never writes is added
  before the table that uses it, with the values from the MySQL source.

Every repair was checked the way --fix's are: the output fails to load or
misbehaves on PostgreSQL 16 before it, loads and behaves after it.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable

from .detectors.statement_trigger import find_statement_trigger
from .plsql_lex import IDENTIFIER, mask_strings_and_comments

# --- statement-level triggers (GAP-118) ------------------------------------


def statement_trigger_names(source: str) -> set[str]:
    return {f.object_name.lower() for f in find_statement_trigger(source)}


def restore_statement_triggers(sql: str, names: set[str]) -> tuple[str, int]:
    count = 0
    for name in names:
        trigger_re = re.compile(
            rf"(CREATE\s+TRIGGER\s+{re.escape(name)}\b[^;]*?\bFOR\s+EACH\s+)ROW\b", re.IGNORECASE
        )
        sql, n = trigger_re.subn(r"\1STATEMENT", sql)
        if n:
            count += n
            function_re = re.compile(
                rf"(CREATE\s+OR\s+REPLACE\s+FUNCTION\s+trigger_fct_{re.escape(name)}\s*\(\s*\).*?\$BODY\$)(.*?)(\$BODY\$)",
                re.IGNORECASE | re.DOTALL,
            )
            sql = function_re.sub(
                lambda m: m.group(1) + re.sub(r"\bRETURN\s+NEW\s*;", "RETURN NULL;", m.group(2), flags=re.IGNORECASE) + m.group(3),
                sql,
            )
    return sql, count


# --- package constants (GAP-114, GAP-119, GAP-036's constants) -------------


@dataclasses.dataclass(frozen=True)
class Constant:
    package: str  # lower case
    name: str  # lower case
    literal: str  # a PostgreSQL literal: 'text' or a number


_PACKAGE_RE = re.compile(
    rf"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:(?:NON)?EDITIONABLE\s+)?PACKAGE(?:\s+BODY)?\s+"
    rf'(?:"?{IDENTIFIER}"?\.)?"?({IDENTIFIER})"?',
    re.IGNORECASE,
)
_ROUTINE_RE = re.compile(r"^\s*(?:FUNCTION|PROCEDURE|CURSOR)\b", re.IGNORECASE | re.MULTILINE)
_CONSTANT_RE = re.compile(
    rf"^[ \t]*({IDENTIFIER})[ \t]+CONSTANT\b[^;:]*?(?::=|\bDEFAULT\b)([^;]*);",
    re.IGNORECASE | re.MULTILINE,
)
_TERM_RE = re.compile(rf"\s*(?:'((?:[^']|'')*)'|(-?\d+(?:\.\d+)?)|({IDENTIFIER}(?:\.{IDENTIFIER})?))\s*")


def _evaluate(expr: str, known: dict[str, str]) -> str | None:
    """The value of a literal, or of a || chain of literals and known
    constants, as plain text; None for anything else."""
    parts: list[str] = []
    pos = 0
    while True:
        m = _TERM_RE.match(expr, pos)
        if m is None:
            return None
        if m.group(1) is not None:
            parts.append(m.group(1).replace("''", "'"))
        elif m.group(2) is not None:
            parts.append(m.group(2))
        else:
            name = m.group(3).lower().rsplit(".", 1)[-1]
            if name not in known:
                return None
            parts.append(known[name])
        pos = m.end()
        if pos >= len(expr):
            break
        if not expr.startswith("||", pos):
            return None
        pos += 2
    return "".join(parts)


def package_constants(source: str) -> list[Constant]:
    """Every package CONSTANT in `source` whose value can be worked out."""
    # Strings must stay readable for the values; comments go.
    masked = mask_strings_and_comments(source)
    constants: list[Constant] = []
    for package in _PACKAGE_RE.finditer(masked):
        start = package.end()
        routine = _ROUTINE_RE.search(masked, start)
        nxt = _PACKAGE_RE.search(masked, start)
        end = min(routine.start() if routine else len(source), nxt.start() if nxt else len(source))
        known: dict[str, str] = {}
        for decl in _CONSTANT_RE.finditer(masked, start, end):
            expr = source[decl.start(2) : decl.end(2)].strip()
            value = _evaluate(expr, known)
            if value is None:
                continue
            name = decl.group(1).lower()
            known[name] = value
            is_number = re.fullmatch(r"-?\d+(?:\.\d+)?", expr) is not None
            literal = value if is_number else "'" + value.replace("'", "''") + "'"
            constants.append(Constant(package.group(1).lower(), name, literal))
    return constants


_CAST = r"::\w+(?:\s*\(\s*\d+(?:\s*,\s*\d+)?\s*\))?"
_ROUTINE_HEAD_RE = re.compile(
    rf"CREATE\s+OR\s+REPLACE\s+(?:FUNCTION|PROCEDURE)\s+({IDENTIFIER})\.{IDENTIFIER}\s*\((.*?)\)\s*(?:RETURNS\b|AS\b)",
    re.IGNORECASE | re.DOTALL,
)


def _constant(literal: str) -> Callable[[re.Match[str]], str]:
    """A replacement that writes `literal` as it is."""
    return lambda _m: literal


def restore_constants(sql: str, constants: list[Constant]) -> tuple[str, int]:
    count = 0
    # GAP-114 first, for every constant: the read spliced with the
    # initializer's pieces and dangling ||s. Replacing plain reads first
    # would turn the spliced pieces into literals and hide the shape. Which
    # pieces ora2pg 25.0 splices in varies from run to run (it walks a Perl
    # hash): for c3 := c2 || 'x', c2 := c1 || 'y' the same input gives
    # `c3::t c2||`, `c3::t c2::t||` or the whole chain, `c3::t c2::t c1::t||||`.
    # One pass over all the constants, leftmost first, so the outermost
    # read of a chain takes its whole spliced tail.
    literals = {f"{c.package}.{c.name}": c.literal for c in constants}
    if literals:
        keys = "|".join(re.escape(k) for k in sorted(literals, key=len, reverse=True))
        # The tail is glued to the cast -- never valid SQL on its own -- and
        # holds what is left of the chain: other reads, names, literals
        # ('xmlns="'||g_ns||, in the Alexandria PL/SQL library), ending in ||.
        spliced = re.compile(
            rf"current_setting\('({keys})'\){_CAST}"
            rf"(?:(?:current_setting\('[^']*'\){_CAST}|[A-Za-z_]\w*|'(?:[^']|'')*')(?:\|\|)*)+(?<=\|\|)",
            re.IGNORECASE,
        )
        sql, n = spliced.subn(lambda m: literals[m.group(1).lower()], sql)
        count += n
    # Then a plain read: nothing ever set_config()s a constant, so the read
    # fails at run time (GAP-036). The cast stays, for the type.
    for c in constants:
        key = re.escape(f"{c.package}.{c.name}")
        read = re.compile(rf"current_setting\('{key}'\)(?={_CAST})", re.IGNORECASE)
        # A function, not the literal itself: a literal is a template to
        # re.sub, and a constant holding a regex ('\w+') would be read as one.
        sql, n = read.subn(_constant(c.literal), sql)
        count += n

    # GAP-119: a parameter DEFAULT naming a constant, bare or qualified.
    by_package: dict[str, dict[str, str]] = {}
    for c in constants:
        by_package.setdefault(c.package, {})[c.name] = c.literal

    def fix_head(m: re.Match[str]) -> str:
        nonlocal count
        names = by_package.get(m.group(1).lower())
        if not names:
            return m.group(0)
        params = m.group(2)

        def fix_default(d: re.Match[str]) -> str:
            nonlocal count
            literal = names.get(d.group(2).lower())
            if literal is None or (d.group(1) and d.group(1).lower().rstrip(".") != m.group(1).lower()):
                return d.group(0)
            count += 1
            return f"DEFAULT {literal}"

        new_params = re.sub(
            rf"\bDEFAULT\s+((?:{IDENTIFIER}\.)?)({IDENTIFIER})\b(?!\s*\()", fix_default, params, flags=re.IGNORECASE
        )
        return m.group(0).replace(params, new_params, 1)

    sql = _ROUTINE_HEAD_RE.sub(fix_head, sql)
    return sql, count


# --- MySQL ENUM types (GAP-068) ---------------------------------------------

_MYSQL_TABLE_RE = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?(?:\w+`?\.`?)?(\w+)`?\s*\(", re.IGNORECASE)
_MYSQL_ENUM_COLUMN_RE = re.compile(r"`?(\w+)`?\s+enum\s*\(((?:\s*'(?:[^'\\]|\\.|'')*'\s*,?)+)\)", re.IGNORECASE)
_ENUM_VALUE_RE = re.compile(r"'((?:[^'\\]|\\.|'')*)'")


def mysql_enum_types(source: str) -> dict[str, str]:
    """type name -> CREATE TYPE statement, for every ENUM column."""
    from .plsql_lex import skip_balanced_parens

    types: dict[str, str] = {}
    for table in _MYSQL_TABLE_RE.finditer(source):
        end = skip_balanced_parens(source, table.end() - 1)
        body = source[table.end() : end]
        for column in _MYSQL_ENUM_COLUMN_RE.finditer(body):
            values = [v.replace("\\'", "''") for v in _ENUM_VALUE_RE.findall(column.group(2))]
            name = f"{table.group(1)}_{column.group(1)}_t".lower()
            types[name] = f"CREATE TYPE {name} AS ENUM ({', '.join(repr_sql(v) for v in values)});"
    return types


def repr_sql(value: str) -> str:
    return "'" + value.replace("''", "'").replace("'", "''") + "'"


def restore_enum_types(sql: str, types: dict[str, str]) -> tuple[str, int]:
    """Add the missing CREATE TYPE for every ENUM type the file uses,
    before the first table that uses it."""
    count = 0
    masked = mask_strings_and_comments(sql)
    for name, create in types.items():
        use = re.search(rf"\b{re.escape(name)}\b", masked, re.IGNORECASE)
        if use is None or re.search(rf"CREATE\s+TYPE\s+{re.escape(name)}\b", masked, re.IGNORECASE):
            continue
        table = masked.rfind("CREATE TABLE", 0, use.start())
        at = table if table != -1 else 0
        sql = sql[:at] + create + "\n" + sql[at:]
        masked = masked[:at] + " " * (len(create) + 1) + masked[at:]
        count += 1
    return sql, count


# --- all of it ---------------------------------------------------------------

# The gaps these repairs take care of, per dialect: fully, or only for
# constants whose value is a literal.
REPAIRED: dict[str, dict[str, str]] = {
    "oracle": {
        "statement_trigger": "all",
        "package_constant_chain": "literal",
        "package_constant_default": "literal",
    },
    "mysql": {"mysql_enum_type": "all"},
}


@dataclasses.dataclass
class SourceKnowledge:
    statement_triggers: set[str]
    constants: list[Constant]
    enum_types: dict[str, str]


def learn(source: str, dialect: str) -> SourceKnowledge:
    if dialect == "mysql":
        return SourceKnowledge(set(), [], mysql_enum_types(source))
    if dialect == "oracle":
        return SourceKnowledge(statement_trigger_names(source), package_constants(source), {})
    return SourceKnowledge(set(), [], {})


def apply(sql: str, knowledge: SourceKnowledge) -> tuple[str, int]:
    total = 0
    for repair in (
        lambda s: restore_statement_triggers(s, knowledge.statement_triggers),
        lambda s: restore_constants(s, knowledge.constants),
        lambda s: restore_enum_types(s, knowledge.enum_types),
    ):
        sql, n = repair(sql)
        total += n
    return sql, total
