import pytest

from ora2pg_gap_report import oracle_connector, oracle_export


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_main_uses_owner_default_from_user(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")
    seen = {}

    def fake_connect(dsn, user, password, lang="ru"):
        seen["connect"] = (dsn, user, password)
        return _FakeConn()

    def fake_export_schema(conn, owner, output_dir, *, types, errors):
        seen["export"] = (owner, output_dir)
        seen["types"] = types
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
        lambda conn, owner, output_dir, **kw: seen.setdefault("owner", owner) and [],
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

    def fake_connect(dsn, user, password, lang="ru"):
        seen["password"] = password
        return _FakeConn()

    monkeypatch.setattr("getpass.getpass", lambda prompt="": "typed-secret")
    monkeypatch.setattr(oracle_connector, "connect", fake_connect)
    monkeypatch.setattr(oracle_connector, "export_schema", lambda conn, owner, output_dir, **kw: [])

    oracle_export.main(
        ["--dsn", "host:1521/orclpdb1", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    assert seen["password"] == "typed-secret"


def test_main_reports_missing_oracledb_driver_gracefully(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")

    def fake_connect(dsn, user, password, lang="ru"):
        raise oracle_connector.OracleDriverMissingError("python-oracledb не установлен.")

    monkeypatch.setattr(oracle_connector, "connect", fake_connect)

    exit_code = oracle_export.main(
        ["--dsn", "host:1521/orclpdb1", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert exit_code == 2
    assert "oracledb" in captured.err


def test_main_reports_connection_failure_without_a_traceback(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")

    def fake_connect(dsn, user, password, lang="ru"):
        raise RuntimeError("DPY-6005: cannot connect to database (unreachable host)")

    monkeypatch.setattr(oracle_connector, "connect", fake_connect)

    exit_code = oracle_export.main(
        ["--dsn", "badhost:1521/orclpdb1", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert exit_code == 3
    assert "Не удалось подключиться" in captured.err
    assert "unreachable host" in captured.err


def test_main_reports_export_failure_without_a_traceback(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")
    monkeypatch.setattr(oracle_connector, "connect", lambda *a, **k: _FakeConn())

    def fake_export_schema(conn, owner, output_dir, *, types, errors):
        raise RuntimeError("ORA-00942: table or view does not exist (ALL_OBJECTS)")

    monkeypatch.setattr(oracle_connector, "export_schema", fake_export_schema)

    exit_code = oracle_export.main(
        ["--dsn", "host:1521/orclpdb1", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    captured = capsys.readouterr()
    assert exit_code == 3
    assert "Ошибка при выгрузке" in captured.err
    assert "ALL_OBJECTS" in captured.err


def test_types_defaults_to_every_exportable_type():
    assert oracle_export._resolve_types(None) == oracle_connector.EXPORTABLE_TYPES


def test_types_selects_named_types_in_registry_order():
    # Typed back to front; the export still writes code objects before
    # schema objects, because the order comes from EXPORTABLE_TYPES.
    chosen = oracle_export._resolve_types("table,trigger")
    assert [t.dictionary_type for t in chosen] == ["TRIGGER", "TABLE"]


def test_types_accepts_a_hyphen_for_a_two_word_type():
    # "PACKAGE BODY" in a comma-separated value would have to be quoted.
    chosen = oracle_export._resolve_types("package-body")
    assert [t.dictionary_type for t in chosen] == ["PACKAGE BODY"]


def test_an_unknown_type_is_rejected_with_the_list_of_valid_ones():
    with pytest.raises(ValueError, match="PROSEDURE"):
        oracle_export._resolve_types("prosedure")


def test_main_rejects_an_unknown_type_without_connecting(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")

    def must_not_connect(*a, **k):
        raise AssertionError("connected despite an invalid --types")

    monkeypatch.setattr(oracle_connector, "connect", must_not_connect)
    exit_code = oracle_export.main(
        ["--dsn", "h:1521/x", "--user", "hr", "--types", "nope", "--output-dir", str(tmp_path)]
    )
    assert exit_code == 2
    assert "NOPE" in capsys.readouterr().err.upper()


def test_main_reports_objects_that_could_not_be_exported(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")
    monkeypatch.setattr(oracle_connector, "connect", lambda *a, **k: _FakeConn())

    def fake_export_schema(conn, owner, output_dir, *, types, errors):
        errors.append(("TABLE", "SECRET_T", RuntimeError("ORA-31603")))
        return []

    monkeypatch.setattr(oracle_connector, "export_schema", fake_export_schema)
    exit_code = oracle_export.main(
        ["--dsn", "h:1521/x", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    err = capsys.readouterr().err
    # A partial export still succeeds -- but what is missing from it is
    # said out loud rather than silently absent.
    assert exit_code == 0
    assert "SECRET_T" in err
    assert "ORA-31603" in err


def test_export_help_is_localized(capsys):
    # The command had no --lang at all, so every string it printed was
    # Russian regardless of what the user had chosen for the rest of the
    # tool. The parser's own help is built from the resolved language,
    # which means the language has to be read off argv before argparse
    # runs -- hence _peek_lang.
    with pytest.raises(SystemExit):
        oracle_export.main(["--lang", "en", "--help"])
    assert "Exports a live Oracle schema" in capsys.readouterr().out

    with pytest.raises(SystemExit):
        oracle_export.main(["--lang", "ru", "--help"])
    assert "Выгружает DDL" in capsys.readouterr().out


def test_peek_lang_reads_both_spellings():
    assert oracle_export._peek_lang(["--lang", "en", "--dsn", "x"]) == "en"
    assert oracle_export._peek_lang(["--lang=en"]) == "en"
    assert oracle_export._peek_lang(["--dsn", "x"]) is None
    # A trailing --lang with no value must not raise here; argparse is
    # what reports that, with its own message.
    assert oracle_export._peek_lang(["--lang"]) is None


def test_export_messages_are_localized(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("ORACLE_PASSWORD", "secret")
    monkeypatch.setattr(oracle_connector, "connect", lambda *a, **k: _FakeConn())
    monkeypatch.setattr(
        oracle_connector, "export_schema",
        lambda conn, owner, output_dir, *, types, errors: [output_dir / "a.sql"],
    )
    oracle_export.main(
        ["--lang", "en", "--dsn", "h:1521/x", "--user", "hr", "--output-dir", str(tmp_path)]
    )
    assert "Exported 1 object(s)" in capsys.readouterr().err


def test_an_unknown_type_is_reported_in_the_chosen_language():
    with pytest.raises(ValueError, match="unknown object type"):
        oracle_export._resolve_types("nope", "en")
    with pytest.raises(ValueError, match="неизвестный тип объекта"):
        oracle_export._resolve_types("nope", "ru")
