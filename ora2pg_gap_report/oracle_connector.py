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
DBMS_METADATA-based offline workflow described in docs/ARCHITECTURE.md.

Required privileges on the target schema: SELECT on ALL_OBJECTS (or the
USER_ equivalent when connecting as the schema owner) and EXECUTE on
DBMS_METADATA (granted via SELECT_CATALOG_ROLE in most environments).
Everything is discovered through ALL_OBJECTS -- triggers used to be
listed from ALL_TRIGGERS, which needed a second grant for a set
ALL_OBJECTS already contains.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

# Type-only: never actually imported at runtime unless _oracledb() below
# does it (lazily, only once a caller has a real reason to need it). With
# `from __future__ import annotations`, every annotation in this module is
# a lazy string, so referencing `oracledb.Connection` in a signature below
# doesn't require oracledb to be installed just to import this module --
# same reasoning as i18n.py's own TYPE_CHECKING-guarded `rich` import.
if TYPE_CHECKING:
    import oracledb


class OracleDriverMissingError(RuntimeError):
    """python-oracledb isn't installed."""


def _oracledb() -> ModuleType:
    try:
        import oracledb
    except ImportError as exc:
        raise OracleDriverMissingError(
            "python-oracledb не установлен. Установите: "
            "pip install ora2pg-gap-report[oracle]"
        ) from exc
    return oracledb


def connect(dsn: str, user: str, password: str) -> oracledb.Connection:
    """Open a connection in oracledb's default thin mode (pure Python, no
    Instant Client). `dsn` is a normal Oracle connect string, e.g.
    "host:1521/ORCLPDB1". Returns the connection as-is — oracledb's own
    connection errors (bad password, unreachable host, ...) propagate
    unwrapped; their messages are already clear."""
    oracledb_module = _oracledb()
    return oracledb_module.connect(user=user, password=password, dsn=dsn)


@dataclasses.dataclass(frozen=True)
class ExportableType:
    """One Oracle object type this module can discover and export.

    Three names for the same thing, because Oracle uses three: what
    ALL_OBJECTS calls it, what DBMS_METADATA.GET_DDL wants as its first
    argument (underscored, and sometimes narrower -- 'PACKAGE_SPEC'
    rather than 'PACKAGE', which would return spec and body together),
    and the file suffix the export writes.
    """

    dictionary_type: str
    metadata_type: str
    suffix: str


# Every type below is one this project's own detectors need to see. The
# original export covered PACKAGE BODY and TRIGGER only, which meant a
# live export was invisible to the whole schema-level half of the
# detectors -- CREATE TABLE clauses, indexes, sequences, synonyms,
# standalone routines, types -- and nothing said so at the point where
# someone would notice. Ordered so a reader sees code objects first,
# then schema objects.
EXPORTABLE_TYPES: tuple[ExportableType, ...] = (
    ExportableType("PACKAGE BODY", "PACKAGE_BODY", ".pkb.sql"),
    # The spec, separately from the body: ACCESSIBLE BY, SUBTYPE ranges
    # and collection/object type declarations live there, not in the body.
    ExportableType("PACKAGE", "PACKAGE_SPEC", ".pks.sql"),
    ExportableType("TRIGGER", "TRIGGER", ".trg.sql"),
    ExportableType("PROCEDURE", "PROCEDURE", ".prc.sql"),
    ExportableType("FUNCTION", "FUNCTION", ".fnc.sql"),
    ExportableType("TYPE", "TYPE_SPEC", ".typ.sql"),
    ExportableType("TYPE BODY", "TYPE_BODY", ".tyb.sql"),
    ExportableType("VIEW", "VIEW", ".vw.sql"),
    ExportableType("MATERIALIZED VIEW", "MATERIALIZED_VIEW", ".mv.sql"),
    ExportableType("TABLE", "TABLE", ".tab.sql"),
    ExportableType("INDEX", "INDEX", ".idx.sql"),
    ExportableType("SEQUENCE", "SEQUENCE", ".seq.sql"),
    ExportableType("SYNONYM", "SYNONYM", ".syn.sql"),
)

# Deliberately absent, so the next reader doesn't assume they were
# forgotten:
#   - MATERIALIZED VIEW LOG. GET_DDL takes the *master table's* name for
#     this type, not the log's own (the log appears in ALL_OBJECTS as a
#     TABLE called MLOG$_...), so it needs a different calling convention
#     than every other row above rather than one more entry.
#   - CONTEXT and DATABASE LINK. Neither is a schema object, so neither
#     is in ALL_OBJECTS at all; they live in ALL_CONTEXT and
#     ALL_DB_LINKS, which are separate queries.
# Both are exportable by hand through get_ddl(), which takes any type
# GET_DDL accepts.

_LIST_OBJECTS_SQL = """
    SELECT object_name
    FROM all_objects
    WHERE object_type = :object_type
      AND owner = :owner
      AND generated = 'N'
      AND subobject_name IS NULL
      AND object_name NOT LIKE 'BIN$%'
    ORDER BY object_name
"""
# Deliberately no `status = 'VALID'` filter: INVALID in Oracle's dictionary
# usually just means "needs recompiling" (a missing grant, a dependency
# that was touched) -- the DDL source is still real code that will need
# migrating regardless. Silently skipping it would make this migration-
# planning tool under-report gaps for exactly the kind of not-pristine
# schema it's built for.
#
# The three filters that ARE here all exclude rows that are not objects
# anyone wrote: `generated = 'N'` drops system-named indexes and
# nested-table storage tables, `subobject_name IS NULL` drops the
# per-partition rows a partitioned table contributes (the table itself is
# already listed once), and the BIN$ exclusion drops the recycle bin.
# Exporting any of them would mean DDL nobody is migrating, and for the
# recycle bin, DDL for objects that have been dropped.

_GET_DDL_SQL = "SELECT DBMS_METADATA.GET_DDL(:object_type, :name, :owner) FROM dual"


def list_objects(conn: oracledb.Connection, owner: str, dictionary_type: str) -> list[str]:
    """Names of `owner`'s objects of one ALL_OBJECTS object_type."""
    with conn.cursor() as cursor:
        cursor.execute(
            _LIST_OBJECTS_SQL,
            object_type=dictionary_type.upper(),
            owner=owner.upper(),
        )
        return [row[0] for row in cursor]


def list_package_bodies(conn: oracledb.Connection, owner: str) -> list[str]:
    return list_objects(conn, owner, "PACKAGE BODY")


def list_triggers(conn: oracledb.Connection, owner: str) -> list[str]:
    return list_objects(conn, owner, "TRIGGER")


def get_ddl(conn: oracledb.Connection, object_type: str, name: str, owner: str) -> str:
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


def export_schema(
    conn: oracledb.Connection,
    owner: str,
    output_dir: Path,
    *,
    types: tuple[ExportableType, ...] = EXPORTABLE_TYPES,
    errors: list[tuple[str, str, Exception]] | None = None,
) -> list[Path]:
    """Export `owner`'s schema as one .sql file per object into
    output_dir. Returns the written paths -- feed them straight into
    `ora2pg-gap-report`.

    Covers every type in EXPORTABLE_TYPES by default; pass `types` to
    narrow it (exporting only PACKAGE BODY and TRIGGER on a schema with
    a hundred thousand tables, say). Everything discovered is a real,
    user-written object: see _LIST_OBJECTS_SQL for what is filtered out
    and why.

    One file per object (not one combined dump) so a partial re-export
    after a schema change only touches the objects that changed, and so a
    single broken object doesn't block collecting the rest.

    `errors` is opt-in isolation, the same contract scan_source() uses:
    pass a list and an object whose GET_DDL raises is skipped, its
    (metadata type, name, exception) landing in `errors` instead of
    aborting the export. Leave it None and the exception propagates, as
    it always did. This matters more here than it looks: GET_DDL raises
    ORA-31603 for an object the connected user can see in ALL_OBJECTS but
    lacks the privilege to read the DDL of, which on a real schema is
    routine rather than exceptional -- and losing an entire export to one
    such object is the opposite of what the per-file design is for."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for object_type in types:
        for name in list_objects(conn, owner, object_type.dictionary_type):
            try:
                ddl = get_ddl(conn, object_type.metadata_type, name, owner)
            except Exception as exc:
                if errors is None:
                    raise
                errors.append((object_type.metadata_type, name, exc))
                continue
            if not ddl:
                # Listed but no DDL: dropped between the list call and
                # this one, or a type GET_DDL declines to render.
                continue
            path = _unique_output_path(output_dir, _safe_stem(name), object_type.suffix)
            path.write_text(ddl, encoding="utf-8")
            written.append(path)

    return written
