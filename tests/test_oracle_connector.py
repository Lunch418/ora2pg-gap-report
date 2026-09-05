import pytest

from ora2pg_gap_report import oracle_connector
from tests.fakes.fake_oracle import FakeConnection, FakeLob

PKG_BODY_ROW = ("LOGGER",)
TRIGGER_ROW = ("TRG_AUDIT",)


def _schema_provider(package_bodies=(), triggers=(), ddl_by_key=None, objects=None,
                     ddl_errors=()):
    """A fake schema. `objects` maps an ALL_OBJECTS object_type to the
    names it holds; `package_bodies`/`triggers` are shorthand for the two
    types every test used before the export covered more than those.

    Dispatches on the object_type bind rather than on the SQL text: there
    is one listing query now, so the bind is the only thing that
    distinguishes one call from another.
    """
    ddl_by_key = ddl_by_key or {}
    by_type = dict(objects or {})
    by_type.setdefault("PACKAGE BODY", list(package_bodies))
    by_type.setdefault("TRIGGER", list(triggers))

    def provider(sql, binds):
        if "all_objects" in sql:
            return [(name,) for name in by_type.get(binds["object_type"], ())]
        if "DBMS_METADATA" in sql:
            key = (binds["object_type"], binds["name"], binds["owner"])
            if key in ddl_errors:
                raise RuntimeError(f"ORA-31603: object {binds['name']} not found")
            value = ddl_by_key.get(key)
            return [(value,)] if value is not None else [(None,)]
        raise AssertionError(f"unexpected SQL in fake: {sql}")

    return provider


def test_list_package_bodies_binds_owner_not_string_formats_it():
    conn = FakeConnection(_schema_provider(package_bodies=["LOGGER", "UTIL_PKG"]))
    names = oracle_connector.list_package_bodies(conn, "hr")

    assert names == ["LOGGER", "UTIL_PKG"]
    sql, binds = conn.calls[0]
    assert binds == {"owner": "HR", "object_type": "PACKAGE BODY"}
    # both values must travel as binds, never interpolated into SQL
    assert "HR" not in sql
    assert "PACKAGE BODY" not in sql


def test_list_package_bodies_does_not_filter_by_status():
    # INVALID in Oracle's dictionary usually just means "needs
    # recompiling" (a missing grant, a touched dependency) — the DDL is
    # still real code that needs migrating. A status filter here would
    # silently under-report gaps on exactly the kind of not-pristine
    # schema this tool exists for.
    conn = FakeConnection(_schema_provider(package_bodies=["LOGGER"]))
    oracle_connector.list_package_bodies(conn, "hr")
    sql, _ = conn.calls[0]
    assert "STATUS" not in sql.upper()


def test_list_triggers_binds_owner():
    conn = FakeConnection(_schema_provider(triggers=["TRG_AUDIT"]))
    names = oracle_connector.list_triggers(conn, "hr")

    assert names == ["TRG_AUDIT"]
    _, binds = conn.calls[0]
    assert binds == {"owner": "HR", "object_type": "TRIGGER"}


def test_get_ddl_reads_a_lob_locator():
    conn = FakeConnection(
        _schema_provider(
            ddl_by_key={("PACKAGE_BODY", "LOGGER", "HR"): FakeLob("CREATE OR REPLACE PACKAGE BODY logger ...")}
        )
    )
    ddl = oracle_connector.get_ddl(conn, "PACKAGE_BODY", "logger", "hr")

    assert ddl == "CREATE OR REPLACE PACKAGE BODY logger ..."
    _, binds = conn.calls[0]
    assert binds == {"object_type": "PACKAGE_BODY", "name": "LOGGER", "owner": "HR"}


def test_get_ddl_accepts_a_plain_string_too():
    # Some oracledb fetch configurations return CLOB columns as plain str
    # rather than a LOB locator — get_ddl must handle both.
    conn = FakeConnection(
        _schema_provider(ddl_by_key={("TRIGGER", "TRG_AUDIT", "HR"): "CREATE OR REPLACE TRIGGER trg_audit ..."})
    )
    ddl = oracle_connector.get_ddl(conn, "TRIGGER", "trg_audit", "hr")
    assert ddl == "CREATE OR REPLACE TRIGGER trg_audit ..."


def test_get_ddl_returns_empty_string_when_object_has_no_ddl():
    conn = FakeConnection(_schema_provider())
    assert oracle_connector.get_ddl(conn, "PACKAGE_BODY", "gone", "hr") == ""


def test_export_schema_writes_one_file_per_object(tmp_path):
    conn = FakeConnection(
        _schema_provider(
            package_bodies=["logger"],
            triggers=["trg_audit"],
            ddl_by_key={
                ("PACKAGE_BODY", "LOGGER", "HR"): "CREATE OR REPLACE PACKAGE BODY logger ...",
                ("TRIGGER", "TRG_AUDIT", "HR"): "CREATE OR REPLACE TRIGGER trg_audit ...",
            },
        )
    )
    output_dir = tmp_path / "export"
    written = oracle_connector.export_schema(conn, "hr", output_dir)

    assert {p.name for p in written} == {"logger.pkb.sql", "trg_audit.trg.sql"}
    assert (output_dir / "logger.pkb.sql").read_text(encoding="utf-8") == "CREATE OR REPLACE PACKAGE BODY logger ..."
    assert (output_dir / "trg_audit.trg.sql").read_text(encoding="utf-8") == "CREATE OR REPLACE TRIGGER trg_audit ..."


def test_export_schema_skips_objects_with_no_ddl(tmp_path):
    # e.g. an object listed but dropped between the list call and GET_DDL
    conn = FakeConnection(_schema_provider(package_bodies=["ghost_pkg"]))
    written = oracle_connector.export_schema(conn, "hr", tmp_path / "export")
    assert written == []


def test_export_schema_writes_utf8_for_non_ascii_ddl(tmp_path):
    # Realistic for the target audience: Cyrillic comments/identifiers in
    # Russian government PL/SQL codebases. Path.write_text() without an
    # explicit encoding falls back to the process locale, which is often
    # ASCII/C on a minimal jump-host container.
    ddl = "-- Комментарий на русском\nCREATE OR REPLACE PACKAGE BODY logger AS END;"
    conn = FakeConnection(
        _schema_provider(package_bodies=["logger"], ddl_by_key={("PACKAGE_BODY", "LOGGER", "HR"): ddl})
    )
    output_dir = tmp_path / "export"
    written = oracle_connector.export_schema(conn, "hr", output_dir)

    assert written[0].read_text(encoding="utf-8") == ddl


def test_export_schema_sanitizes_object_names_used_as_filenames(tmp_path):
    # Oracle quoted identifiers can contain almost anything, including '/'
    # and '..' — an object name must never be trusted as a filesystem path
    # component on its own.
    conn = FakeConnection(
        _schema_provider(
            package_bodies=["../../evil"],
            ddl_by_key={("PACKAGE_BODY", "../../EVIL", "HR"): "CREATE OR REPLACE PACKAGE BODY x AS END;"},
        )
    )
    output_dir = tmp_path / "export"
    written = oracle_connector.export_schema(conn, "hr", output_dir)

    assert len(written) == 1
    resolved = written[0].resolve()
    assert output_dir.resolve() in resolved.parents
    assert resolved.name != "../../evil"


def test_export_schema_disambiguates_filename_collisions(tmp_path):
    # Two distinct quoted objects that collide once sanitized/lowercased
    # (e.g. "Logger" vs "LOGGER") must not silently overwrite each other.
    conn = FakeConnection(
        _schema_provider(
            package_bodies=["Logger", "LOGGER"],
            ddl_by_key={
                ("PACKAGE_BODY", "LOGGER", "HR"): "-- ambiguous: could be either object",
            },
        )
    )
    output_dir = tmp_path / "export"
    written = oracle_connector.export_schema(conn, "hr", output_dir)

    assert len(written) == 2
    assert len({p.name for p in written}) == 2  # distinct filenames, nothing overwritten


def test_export_schema_covers_schema_level_objects_not_just_code(tmp_path):
    # The point of EXPORTABLE_TYPES: before it, a live export produced
    # only PACKAGE BODY and TRIGGER files, so every schema-level detector
    # -- table clauses, indexes, sequences, synonyms, standalone routines,
    # types -- saw an empty schema and reported nothing.
    conn = FakeConnection(
        _schema_provider(
            objects={
                "TABLE": ["employees"],
                "INDEX": ["idx_emp_gender"],
                "SEQUENCE": ["emp_seq"],
                "SYNONYM": ["emp"],
                "TYPE": ["addr_t"],
                "PROCEDURE": ["do_thing"],
                "FUNCTION": ["calc"],
                "VIEW": ["v_emp"],
                "PACKAGE": ["logger"],
            },
            ddl_by_key={
                ("TABLE", "EMPLOYEES", "HR"): "CREATE TABLE employees (id NUMBER) READ ONLY;",
                ("INDEX", "IDX_EMP_GENDER", "HR"): "CREATE BITMAP INDEX idx_emp_gender ON employees (gender);",
                ("SEQUENCE", "EMP_SEQ", "HR"): "CREATE SEQUENCE emp_seq CYCLE;",
                ("SYNONYM", "EMP", "HR"): "CREATE PUBLIC SYNONYM emp FOR hr.employees;",
                ("TYPE_SPEC", "ADDR_T", "HR"): "CREATE TYPE addr_t AS OBJECT (city VARCHAR2(50));",
                ("PROCEDURE", "DO_THING", "HR"): "CREATE PROCEDURE do_thing AS BEGIN NULL; END;",
                ("FUNCTION", "CALC", "HR"): "CREATE FUNCTION calc RETURN NUMBER AS BEGIN RETURN 1; END;",
                ("VIEW", "V_EMP", "HR"): "CREATE VIEW v_emp AS SELECT * FROM employees WITH READ ONLY;",
                ("PACKAGE_SPEC", "LOGGER", "HR"): "CREATE PACKAGE logger AS END;",
            },
        )
    )
    written = oracle_connector.export_schema(conn, "hr", tmp_path / "export")

    assert {p.name for p in written} == {
        "logger.pks.sql", "do_thing.prc.sql", "calc.fnc.sql", "addr_t.typ.sql",
        "v_emp.vw.sql", "employees.tab.sql", "idx_emp_gender.idx.sql",
        "emp_seq.seq.sql", "emp.syn.sql",
    }


def test_export_schema_output_is_actually_scannable(tmp_path):
    # End to end on the part that matters: DDL this exporter writes must
    # be something the detectors then find gaps in. A table exported with
    # no findings would mean the export and the detectors disagree about
    # what Oracle DDL looks like.
    from ora2pg_gap_report.core import scan_source

    ddl = "CREATE TABLE employees (id NUMBER) READ ONLY;"
    conn = FakeConnection(
        _schema_provider(
            objects={"TABLE": ["employees"]},
            ddl_by_key={("TABLE", "EMPLOYEES", "HR"): ddl},
        )
    )
    written = oracle_connector.export_schema(conn, "hr", tmp_path / "export")
    findings = scan_source(written[0].read_text(encoding="utf-8"))

    assert "read_only_table" in {f.detector for f in findings}


def test_export_schema_can_be_narrowed_to_some_types(tmp_path):
    conn = FakeConnection(
        _schema_provider(
            objects={"TABLE": ["employees"], "TRIGGER": ["trg_audit"]},
            ddl_by_key={
                ("TABLE", "EMPLOYEES", "HR"): "CREATE TABLE employees (id NUMBER);",
                ("TRIGGER", "TRG_AUDIT", "HR"): "CREATE TRIGGER trg_audit ...",
            },
        )
    )
    only_triggers = tuple(
        t for t in oracle_connector.EXPORTABLE_TYPES if t.dictionary_type == "TRIGGER"
    )
    written = oracle_connector.export_schema(
        conn, "hr", tmp_path / "export", types=only_triggers
    )
    assert {p.name for p in written} == {"trg_audit.trg.sql"}


def test_export_schema_skips_system_generated_and_recycled_objects(tmp_path):
    # Not filtered in Python but in the query, so this asserts on the SQL:
    # ALL_OBJECTS carries system-named indexes, per-partition rows and the
    # recycle bin, none of which anyone is migrating.
    conn = FakeConnection(_schema_provider())
    oracle_connector.list_objects(conn, "hr", "TABLE")
    sql, _ = conn.calls[0]
    assert "generated = 'N'" in sql
    assert "subobject_name IS NULL" in sql
    assert "BIN$" in sql


def test_export_schema_still_exports_invalid_objects(tmp_path):
    # INVALID usually means "needs recompiling", not "not real code".
    conn = FakeConnection(_schema_provider())
    oracle_connector.list_objects(conn, "hr", "PACKAGE BODY")
    sql, _ = conn.calls[0]
    assert "STATUS" not in sql.upper()


def test_export_schema_isolates_one_objects_failure_when_asked(tmp_path):
    # GET_DDL raises ORA-31603 for an object visible in ALL_OBJECTS whose
    # DDL the connected user may not read -- routine on a real schema.
    # Losing the whole export to it defeats the per-file design.
    conn = FakeConnection(
        _schema_provider(
            objects={"TABLE": ["forbidden", "readable"]},
            ddl_by_key={("TABLE", "READABLE", "HR"): "CREATE TABLE readable (id NUMBER);"},
            ddl_errors={("TABLE", "FORBIDDEN", "HR")},
        )
    )
    errors: list[tuple[str, str, Exception]] = []
    written = oracle_connector.export_schema(
        conn, "hr", tmp_path / "export", errors=errors
    )

    assert {p.name for p in written} == {"readable.tab.sql"}
    # The name as ALL_OBJECTS listed it -- that is what identifies the
    # object to whoever reads the error, not the uppercased bind value.
    assert [(t, n) for t, n, _ in errors] == [("TABLE", "forbidden")]


def test_export_schema_propagates_a_failure_when_errors_is_not_passed(tmp_path):
    # The original contract, unchanged for every caller that doesn't opt in.
    conn = FakeConnection(
        _schema_provider(
            objects={"TABLE": ["forbidden"]},
            ddl_errors={("TABLE", "FORBIDDEN", "HR")},
        )
    )
    with pytest.raises(RuntimeError, match="ORA-31603"):
        oracle_connector.export_schema(conn, "hr", tmp_path / "export")


def test_every_exportable_type_has_a_distinct_suffix():
    suffixes = [t.suffix for t in oracle_connector.EXPORTABLE_TYPES]
    assert len(suffixes) == len(set(suffixes))


def test_connect_raises_a_clear_error_when_oracledb_is_missing(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "oracledb":
            raise ImportError("no module named oracledb")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(oracle_connector.OracleDriverMissingError):
        oracle_connector.connect("host:1521/orclpdb1", "hr", "secret")


@pytest.mark.skipif(
    "ORACLE_DSN" not in __import__("os").environ,
    reason="no live Oracle instance configured (set ORACLE_DSN/ORACLE_USER/ORACLE_PASSWORD)",
)
def test_live_integration_smoke(tmp_path):
    import os

    conn = oracle_connector.connect(
        os.environ["ORACLE_DSN"], os.environ["ORACLE_USER"], os.environ["ORACLE_PASSWORD"]
    )
    with conn:
        written = oracle_connector.export_schema(conn, os.environ["ORACLE_USER"], tmp_path)
    assert isinstance(written, list)
