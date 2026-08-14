from pathlib import Path

import pytest

from ora2pg_gap_report import oracle_connector
from tests.fakes.fake_oracle import FakeConnection, FakeLob

PKG_BODY_ROW = ("LOGGER",)
TRIGGER_ROW = ("TRG_AUDIT",)


def _schema_provider(package_bodies=(), triggers=(), ddl_by_key=None):
    ddl_by_key = ddl_by_key or {}

    def provider(sql, binds):
        if "PACKAGE BODY" in sql:
            return [(name,) for name in package_bodies]
        if "all_triggers" in sql:
            return [(name,) for name in triggers]
        if "DBMS_METADATA" in sql:
            key = (binds["object_type"], binds["name"], binds["owner"])
            value = ddl_by_key.get(key)
            return [(value,)] if value is not None else [(None,)]
        raise AssertionError(f"unexpected SQL in fake: {sql}")

    return provider


def test_list_package_bodies_binds_owner_not_string_formats_it():
    conn = FakeConnection(_schema_provider(package_bodies=["LOGGER", "UTIL_PKG"]))
    names = oracle_connector.list_package_bodies(conn, "hr")

    assert names == ["LOGGER", "UTIL_PKG"]
    sql, binds = conn.calls[0]
    assert binds == {"owner": "HR"}
    # the owner value must travel as a bind, never interpolated into SQL
    assert "HR" not in sql


def test_list_triggers_binds_owner():
    conn = FakeConnection(_schema_provider(triggers=["TRG_AUDIT"]))
    names = oracle_connector.list_triggers(conn, "hr")

    assert names == ["TRG_AUDIT"]
    _, binds = conn.calls[0]
    assert binds == {"owner": "HR"}


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
    assert (output_dir / "logger.pkb.sql").read_text() == "CREATE OR REPLACE PACKAGE BODY logger ..."
    assert (output_dir / "trg_audit.trg.sql").read_text() == "CREATE OR REPLACE TRIGGER trg_audit ..."


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
