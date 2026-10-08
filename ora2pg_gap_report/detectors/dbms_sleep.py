import re

from ..models import Finding
from ..plsql_lex import line_at, mask_strings_and_comments
from .supplied_package_call import statement_calls

_SLEEP_RE = re.compile(r"^DBMS_(?:LOCK|SESSION)\.SLEEP$", re.IGNORECASE)


def find_dbms_sleep(source: str) -> list[Finding]:
    """Detect DBMS_LOCK.SLEEP / DBMS_SESSION.SLEEP called as a statement.

    ora2pg 25.0 has two rules for it in PLSQL.pm: `PERFORM pg_sleep` in
    plsql_to_plpgsql, and a bare `pg_sleep` in replace_oracle_function --
    which runs first, so the PERFORM rule never matches. The output is
    `pg_sleep(1);`, and PL/pgSQL rejects a function called as a statement
    without PERFORM ('syntax error at or near "pg_sleep"'): the routine
    does not load. Oracle 23ai runs the original. --fix writes the PERFORM.
    See docs/research/gap-123-dbms-sleep.md."""
    clean = mask_strings_and_comments(source)
    return [
        Finding(
            detector="dbms_sleep",
            severity="high",
            object_name=f"{m.group(2)}.{m.group(3)}".upper(),
            line=line_at(clean, m.start(1)),
            snippet=f"{m.group(2)}.{m.group(3)}".upper(),
            message_id="dbms_sleep",
        )
        for m in statement_calls(clean)
        if _SLEEP_RE.match(f"{m.group(2)}.{m.group(3)}")
    ]
