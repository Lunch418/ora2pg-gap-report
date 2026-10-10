from ..models import Finding
from ..mssql_lex import enclosing_object_name, enclosing_object_name_index, mask_strings_and_comments
from ..plsql_lex import line_at
from ..rollup import WITH_ROLLUP_RE


def find_mssql_with_rollup(source: str) -> list[Finding]:
    """Detect T-SQL's GROUP BY a, b WITH ROLLUP (and WITH CUBE), the old
    form of GROUP BY ROLLUP (a, b).

    ora2pg 25.0 (-M) copies it, and PostgreSQL 16 knows only GROUP BY
    ROLLUP (a, b) ('syntax error at or near "with"') -- the routine or
    view does not load. Found in Microsoft's pubs (three procedures).
    --fix rewrites it. See
    docs/research/gap-151-mssql-with-rollup.md."""
    if "WITH" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    return [
        Finding(
            detector="mssql_with_rollup",
            severity="high",
            object_name=enclosing_object_name(index, m.start()),
            line=line_at(clean, m.start()),
            snippet=f"GROUP BY ... WITH {m.group('kind').upper()}",
            message_id="mssql_with_rollup",
        )
        for m in WITH_ROLLUP_RE.finditer(clean)
    ]
