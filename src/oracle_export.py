"""CLI: export a live Oracle schema's DDL to flat files for offline
analysis via `python -m src.cli`.

Deliberately a separate entry point from cli.py, not a flag on it: the
export step needs live Oracle network access; the analysis step (all four
detectors) never does. In a closed contour those two things often happen
on different machines (a jump host with DB access vs. an isolated
workstation) — keeping them as separate commands means the exported .sql
files are the only thing that has to cross that boundary.
"""

import argparse
import getpass
import os
import sys
from pathlib import Path

from . import oracle_connector


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oracle-export",
        description=(
            "Выгружает DDL PACKAGE BODY и TRIGGER из живой Oracle-схемы "
            "в отдельные .sql файлы — для последующего анализа через "
            "`python -m src.cli`."
        ),
    )
    parser.add_argument("--dsn", required=True, help="Oracle connect string, напр. host:1521/ORCLPDB1")
    parser.add_argument("--user", required=True)
    parser.add_argument(
        "--owner",
        default=None,
        help="Схема, из которой выгружать объекты (по умолчанию — совпадает с --user)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("oracle_export"),
        help="Куда сохранить .sql файлы (по умолчанию — ./oracle_export)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    owner = args.owner or args.user

    # Never accept the password as a CLI argument — it would be visible to
    # anyone on the box via `ps`. Env var for scripted use, prompt otherwise.
    password = os.environ.get("ORACLE_PASSWORD") or getpass.getpass("Oracle password: ")

    try:
        conn = oracle_connector.connect(args.dsn, args.user, password)
    except oracle_connector.OracleDriverMissingError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        # Deliberately broad, unlike the rest of this codebase: this is the
        # one operation that talks to an external, unreliable, network-
        # dependent service. An operator on a jump host needs "wrong
        # password" / "host unreachable", not a Python traceback.
        print(f"Не удалось подключиться к Oracle: {exc}", file=sys.stderr)
        return 3

    try:
        with conn:
            written = oracle_connector.export_schema(conn, owner, args.output_dir)
    except Exception as exc:
        print(f"Ошибка при выгрузке схемы: {exc}", file=sys.stderr)
        return 3

    print(f"Экспортировано {len(written)} объект(ов) в {args.output_dir}/", file=sys.stderr)
    for path in written:
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
