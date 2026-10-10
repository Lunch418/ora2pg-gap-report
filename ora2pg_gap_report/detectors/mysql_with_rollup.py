from ..models import Finding
from ..mysql_lex import enclosing_object_name, enclosing_object_name_index, line_at, mask_strings_and_comments
from ..rollup import WITH_ROLLUP_RE


def find_mysql_with_rollup(source: str) -> list[Finding]:
    """Detect MySQL's GROUP BY a, b WITH ROLLUP, the old form of GROUP BY
    ROLLUP (a, b).

    ora2pg 25.0 (-m) copies it into views and routines, and PostgreSQL 16
    knows only GROUP BY ROLLUP (a, b) ('syntax error at or near "WITH"')
    -- the view or routine does not load. --fix rewrites it. See
    docs/research/gap-152-mysql-with-rollup.md."""
    if "WITH" not in source.upper():
        return []
    clean = mask_strings_and_comments(source)
    index = enclosing_object_name_index(clean)
    return [
        Finding(
            detector="mysql_with_rollup",
            severity="high",
            object_name=enclosing_object_name(index, m.start()),
            line=line_at(clean, m.start()),
            snippet=f"GROUP BY ... WITH {m.group('kind').upper()}",
            message_id="mysql_with_rollup",
        )
        for m in WITH_ROLLUP_RE.finditer(clean)
    ]
