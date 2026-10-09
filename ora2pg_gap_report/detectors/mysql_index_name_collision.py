from ..models import Finding
from ..mysql_indexes import bare, colliding_names, index_clauses
from ..mysql_lex import line_at, mask_strings_and_comments


def find_mysql_index_name_collision(source: str) -> list[Finding]:
    """Detect an index name used on more than one table: `KEY customer_id
    (customer_id)` in both `orders` and `invoices` -- fine in MySQL, where
    an index name belongs to its table, and common in mysqldump output.

    In PostgreSQL an index name belongs to the schema. ora2pg 25.0 (-m)
    keeps the names, so the second CREATE INDEX fails ('relation
    "customer_id" already exists') and that table is left without the
    index. --prepare renames the clashing ones to <table>_<name>. See
    docs/research/gap-128-mysql-index-name-collision.md.

    Reported at every use after the first table's."""
    clean = mask_strings_and_comments(source)
    clauses = index_clauses(source)
    clashes = colliding_names(clauses)
    first_table: dict[str, str] = {}
    findings: list[Finding] = []
    for clause in clauses:
        if clause.qualifier is not None or clause.name is None:
            continue
        name = bare(clause.name).lower()
        if name not in clashes:
            continue
        owner = first_table.setdefault(name, clause.table.lower())
        if owner == clause.table.lower():
            continue
        findings.append(
            Finding(
                detector="mysql_index_name_collision",
                severity="high",
                object_name=clause.table,
                line=line_at(clean, clause.start),
                snippet=bare(clause.name),
                message_id="mysql_index_name_collision",
            )
        )
    return findings
