"""source_text.py: a source file read whatever Unicode encoding it is in
-- SSMS saves scripts as UTF-16, and read as UTF-8 such a file scanned
clean, every other byte a NUL (Microsoft's Wide World Importers samples)."""

import json

import pytest

from ora2pg_gap_report.cli import main
from ora2pg_gap_report.source_text import decode_source, detect_encoding, encode_source

SCRIPT = "CREATE TABLE t (id INT IDENTITY(1,1), note NVARCHAR(10))\nGO\nCREATE INDEX ix ON t(note)\nGO\n"


@pytest.mark.parametrize(
    ("data", "encoding"),
    [
        (b"\xff\xfe" + "SELECT 1".encode("utf-16-le"), "utf-16-le-bom"),
        (b"\xfe\xff" + "SELECT 1".encode("utf-16-be"), "utf-16-be-bom"),
        ("SELECT 1;".encode("utf-16-le"), "utf-16-le"),
        ("SELECT 1;".encode("utf-16-be"), "utf-16-be"),
        (b"\xff\xfe\x00\x00" + "SELECT 1".encode("utf-32-le"), "utf-32-le-bom"),
        (b"\xef\xbb\xbfSELECT 1", "utf-8"),
        ("SELECT 'пример'".encode("utf-8"), "utf-8"),
    ],
)
def test_encodings_are_told_apart(data, encoding):
    assert detect_encoding(data) == encoding
    text, found = decode_source(data)
    assert "SELECT" in text and found == encoding
    assert encode_source(text, found) == data


def test_bytes_that_are_not_utf8_survive_a_rewrite():
    data = "-- коммент\n".encode("cp1251")
    text, encoding = decode_source(data, errors="surrogateescape")
    assert encode_source(text, encoding) == data


def _scan(tmp_path, capsys, data):
    path = tmp_path / "script.sql"
    path.write_bytes(data)
    assert main(["--dialect", "mssql", "-f", "json", str(path)]) == 0
    return sorted(f["detector"] for f in json.loads(capsys.readouterr().out)["findings"])


def test_a_utf16_script_is_scanned_like_a_utf8_one(tmp_path, capsys):
    utf8 = _scan(tmp_path, capsys, SCRIPT.encode("utf-8"))
    assert utf8  # the script has findings at all
    assert _scan(tmp_path, capsys, SCRIPT.encode("utf-16")) == utf8
    assert _scan(tmp_path, capsys, SCRIPT.encode("utf-16-le")) == utf8


def test_prepare_writes_a_utf16_script_back_as_utf16(tmp_path, capsys):
    path = tmp_path / "script.sql"
    path.write_bytes(SCRIPT.encode("utf-16"))
    assert main(["--prepare", "--dialect", "mssql", "--write", str(path)]) == 0
    data = path.read_bytes()
    assert data.startswith(b"\xff\xfe")
    text = data.decode("utf-16")
    assert "GO" not in text and "CREATE INDEX ix ON t(note);" in text
