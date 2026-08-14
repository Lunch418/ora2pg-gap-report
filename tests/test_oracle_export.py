from pathlib import Path

import pytest

from src import oracle_connector, oracle_export


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_main_uses_owner_default_from_user(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")
    seen = {}

    def fake_connect(dsn, user, password):
        seen["connect"] = (dsn, user, password)
        return _FakeConn()

    def fake_export_schema(conn, owner, output_dir):
        seen["export"] = (owner, output_dir)
        return [output_dir / "logger.pkb.sql"]

    monkeypatch.setattr(oracle_connector, "connect", fake_connect)
    monkeypatch.setattr(oracle_connector, "export_schema", fake_export_schema)

    exit_code = oracle_export.main(
        ["--dsn", "host:1521/orclpdb1", "--user", "hr", "--output-dir", str(tmp_path / "out")]
    )

    assert exit_code == 0
    assert seen["connect"] == ("host:1521/orclpdb1", "hr", "secret")
    assert seen["export"][0] == "hr"  # owner defaulted to --user


def test_main_explicit_owner_overrides_user(monkeypatch, tmp_path):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")
    seen = {}
    monkeypatch.setattr(oracle_connector, "connect", lambda *a, **k: _FakeConn())
    monkeypatch.setattr(
        oracle_connector,
        "export_schema",
        lambda conn, owner, output_dir: seen.setdefault("owner", owner) and [],
    )

    oracle_export.main(
        [
            "--dsn", "host:1521/orclpdb1",
            "--user", "migration_svc",
            "--owner", "hr",
            "--output-dir", str(tmp_path),
        ]
    )
    assert seen["owner"] == "hr"


def test_main_prompts_for_password_when_env_var_absent(monkeypatch, tmp_path):
    monkeypatch.delenv("ORACLE_PASSWORD", raising=False)
    seen = {}

    def fake_connect(dsn, user, password):
        seen["password"] = password
        return _FakeConn()

    monkeypatch.setattr("getpass.getpass", lambda prompt="": "typed-secret")
    monkeypatch.setattr(oracle_connector, "connect", fake_connect)
    monkeypatch.setattr(oracle_connector, "export_schema", lambda conn, owner, output_dir: [])

    oracle_export.main(
        ["--dsn", "host:1521/orclpdb1", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    assert seen["password"] == "typed-secret"


def test_main_reports_missing_oracledb_driver_gracefully(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")

    def fake_connect(dsn, user, password):
        raise oracle_connector.OracleDriverMissingError("python-oracledb не установлен.")

    monkeypatch.setattr(oracle_connector, "connect", fake_connect)

    exit_code = oracle_export.main(
        ["--dsn", "host:1521/orclpdb1", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "oracledb" in captured.err
