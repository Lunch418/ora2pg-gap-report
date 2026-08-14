"""Live Oracle metadata extraction.

Uses `python-oracledb` in its default "thin" mode — pure Python, no Oracle
Instant Client to install. That matters for this project's audience: a
PAM jump host in a closed contour is exactly the kind of place you can't
casually install a native Oracle client onto.

Optional dependency: not required by the base package (the rest of the
project is pure stdlib + an optional external `ora2pg`). Install with
`pip install ora2pg-gap-report[oracle]`. `connect()` is the only function
that actually imports oracledb — every
other function here takes an already-open connection, so this module
stays importable (and testable against a fake connection) without
oracledb installed at all.

Extracts DDL via DBMS_METADATA.GET_DDL rather than reassembling ALL_SOURCE
line by line — it's the same approach `expdp` uses under the hood, and it
produces DDL text you could hand to ora2pg directly, matching the
DBMS_METADATA-based offline workflow described in PROJECT_BRIEF.md.

Required privileges on the target schema: SELECT on ALL_OBJECTS and
ALL_TRIGGERS (or the USER_ equivalents when connecting as the schema
owner), and EXECUTE on DBMS_METADATA (granted via SELECT_CATALOG_ROLE in
most environments).
"""

import re
from pathlib import Path


class OracleDriverMissingError(RuntimeError):
    """python-oracledb isn't installed."""


def _oracledb():
    try:
        import oracledb
    except ImportError as exc:
        raise OracleDriverMissingError(
            "python-oracledb не установлен. Установите: "
            "pip install ora2pg-gap-report[oracle]"
        ) from exc
    return oracledb


def connect(dsn: str, user: str, password: str):
    """Open a connection in oracledb's default thin mode (pure Python, no
    Instant Client). `dsn` is a normal Oracle connect string, e.g.
    "host:1521/ORCLPDB1". Returns the connection as-is — oracledb's own
    connection errors (bad password, unreachable host, ...) propagate
    unwrapped; their messages are already clear."""
    oracledb = _oracledb()
    return oracledb.connect(user=user, password=password, dsn=dsn)


_LIST_PACKAGE_BODIES_SQL = """
    SELECT object_name
    FROM all_objects
    WHERE object_type = 'PACKAGE BODY'
      AND owner = :owner
      AND status = 'VALID'
    ORDER BY object_name
"""

_LIST_TRIGGERS_SQL = """
    SELECT trigger_name
    FROM all_triggers
    WHERE owner = :owner
    ORDER BY trigger_name
"""

_GET_DDL_SQL = "SELECT DBMS_METADATA.GET_DDL(:object_type, :name, :owner) FROM dual"


def list_package_bodies(conn, owner: str) -> list[str]:
    with conn.cursor() as cursor:
        cursor.execute(_LIST_PACKAGE_BODIES_SQL, owner=owner.upper())
        return [row[0] for row in cursor]


def list_triggers(conn, owner: str) -> list[str]:
    with conn.cursor() as cursor:
        cursor.execute(_LIST_TRIGGERS_SQL, owner=owner.upper())
        return [row[0] for row in cursor]


def get_ddl(conn, object_type: str, name: str, owner: str) -> str:
    """object_type is a DBMS_METADATA object type string — 'PACKAGE_BODY'
    or 'TRIGGER' for what this module lists, but any type GET_DDL accepts
    works. Returns "" if the object has no DDL (shouldn't happen for a
    name just listed by list_package_bodies/list_triggers, but a schema
    can change between the list call and this one)."""
    with conn.cursor() as cursor:
        cursor.execute(
            _GET_DDL_SQL,
            object_type=object_type,
            name=name.upper(),
            owner=owner.upper(),
        )
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return ""
        value = row[0]
        # DBMS_METADATA.GET_DDL returns a CLOB; depending on oracledb's
        # fetch configuration that arrives as a LOB locator (needs .read())
        # or already as a plain str — handle both rather than assuming one.
        return value.read() if hasattr(value, "read") else str(value)


_UNSAFE_FILENAME_CHAR_RE = re.compile(r"[^A-Za-z0-9_$#]")


def _safe_stem(name: str) -> str:
    """Sanitize an Oracle object name into a filename component. Oracle
    quoted identifiers can contain almost anything, including '/' and
    '..' — object names come straight from the database and must never be
    trusted as filesystem-safe on their own (path traversal)."""
    sanitized = _UNSAFE_FILENAME_CHAR_RE.sub("_", name).strip("_")
    return (sanitized or "_").lower()


def _unique_output_path(output_dir: Path, stem: str, suffix: str) -> Path:
    """Sanitizing distinct quoted names (e.g. "Logger" vs "LOGGER") can
    make them collide once lowercased — never silently overwrite one
    object's export with another's."""
    candidate = output_dir / f"{stem}{suffix}"
    n = 2
    while candidate.exists():
        candidate = output_dir / f"{stem}_{n}{suffix}"
        n += 1
    return candidate


def export_schema(conn, owner: str, output_dir: Path) -> list[Path]:
    """Export every PACKAGE BODY and TRIGGER in `owner`'s schema as one
    .sql file per object into output_dir. Returns the written paths — feed
    them straight into `ora2pg-gap-report`.

    One file per object (not one combined dump) so a partial re-export
    after a schema change only touches the objects that changed, and so a
    single broken object doesn't block collecting the rest."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for name in list_package_bodies(conn, owner):
        ddl = get_ddl(conn, "PACKAGE_BODY", name, owner)
        if not ddl:
            continue
        path = _unique_output_path(output_dir, _safe_stem(name), ".pkb.sql")
        path.write_text(ddl, encoding="utf-8")
        written.append(path)

    for name in list_triggers(conn, owner):
        ddl = get_ddl(conn, "TRIGGER", name, owner)
        if not ddl:
            continue
        path = _unique_output_path(output_dir, _safe_stem(name), ".trg.sql")
        path.write_text(ddl, encoding="utf-8")
        written.append(path)

    return written
