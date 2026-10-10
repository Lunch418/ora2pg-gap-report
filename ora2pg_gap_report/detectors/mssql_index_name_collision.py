import re

from ..models import Finding
from ..mssql_lex import mask_strings_and_comments, normalize_name
from ..plsql_lex import line_at

_NAME = r'(?:\[[^\]]*\]|"[^"]*"|[A-Za-z_@#][\w@#$]*)'
INDEX_RE = re.compile(
    rf"\bCREATE\s+(?:UNIQUE\s+)?(?:(?:NON)?CLUSTERED\s+)?INDEX\s+({_NAME})\s+ON\s+((?:{_NAME}\s*\.\s*)*{_NAME})",
    re.IGNORECASE,
)


def index_statements(clean: str) -> list[re.Match[str]]:
    return list(INDEX_RE.finditer(clean))


def table_of(m: re.Match[str]) -> str:
    """The index's table, bare and lower case."""
    return normalize_name(re.split(r"\s*\.\s*", m.group(2))[-1]).lower()


def find_mssql_index_name_collision(source: str) -> list[Finding]:
    """Detect an index name used on more than one table: `CREATE INDEX
    idx_fk_store_id ON customer(...)` and `... ON staff(...)`.

    In SQL Server an index name belongs to its table; in PostgreSQL to the
    schema. ora2pg 25.0 (-M) keeps the names, so the second CREATE INDEX
    fails ('relation "idx_fk_store_id" already exists') and that table has
    no index. Found in jOOQ's Sakila (five) and Microsoft's pubs
    (titleidind). --prepare renames the later ones to <table>_<name>, as
    for MySQL (GAP-128). See docs/research/gap-150-mssql-index-name-collision.md.

    Reported at every use after the first table's."""
    if "INDEX" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    owner: dict[str, str] = {}
    findings: list[Finding] = []
    for m in index_statements(clean):
        name = normalize_name(m.group(1)).lower()
        table = table_of(m)
        if owner.setdefault(name, table) == table:
            continue
        findings.append(
            Finding(
                detector="mssql_index_name_collision",
                severity="high",
                object_name=table.upper(),
                line=line_at(clean, m.start()),
                snippet=normalize_name(m.group(1)),
                message_id="mssql_index_name_collision",
            )
        )
    return findings
