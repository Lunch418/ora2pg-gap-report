"""CLI: export a live Oracle schema's DDL to flat files for offline
analysis via `ora2pg-gap-report`.

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

# ALL_OBJECTS spells some of these with a space ("PACKAGE BODY"); accept a
# hyphen too, since a comma-separated CLI value with embedded spaces has
# to be quoted and that trips people up.
_TYPE_CHOICES = ", ".join(t.dictionary_type for t in oracle_connector.EXPORTABLE_TYPES)


def _resolve_types(raw: str | None) -> tuple[oracle_connector.ExportableType, ...]:
    """The EXPORTABLE_TYPES named by a --types value, or all of them."""
    if raw is None:
        return oracle_connector.EXPORTABLE_TYPES
    wanted = [name.strip().upper().replace("-", " ") for name in raw.split(",") if name.strip()]
    by_name = {t.dictionary_type: t for t in oracle_connector.EXPORTABLE_TYPES}
    unknown = [name for name in wanted if name not in by_name]
    if unknown:
        raise ValueError(
            f"неизвестный тип объекта: {', '.join(unknown)}. Доступны: {_TYPE_CHOICES}"
        )
    # Keep EXPORTABLE_TYPES' own order, not the order they were typed in,
    # so the export writes code objects before schema objects either way.
    return tuple(t for t in oracle_connector.EXPORTABLE_TYPES if t.dictionary_type in wanted)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ora2pg-gap-export",
        description=(
            "Выгружает DDL объектов живой Oracle-схемы в отдельные .sql "
            "файлы — для последующего анализа через `ora2pg-gap-report`."
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
        "--types",
        default=None,
        metavar="TYPE,...",
        help=(
            "Какие типы объектов выгружать, через запятую "
            f"(по умолчанию все: {_TYPE_CHOICES}). Имена — как в "
            "ALL_OBJECTS.object_type, регистр не важен"
        ),
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

    try:
        types = _resolve_types(args.types)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

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

    # Per-object isolation: GET_DDL raises for an object the connected
    # user can see in ALL_OBJECTS but may not read the DDL of, which on a
    # real schema is routine. Reported at the end rather than aborting --
    # a partial export is worth far more than none, as long as what is
    # missing from it is said out loud.
    errors: list[tuple[str, str, Exception]] = []
    try:
        with conn:
            written = oracle_connector.export_schema(
                conn, owner, args.output_dir, types=types, errors=errors
            )
    except Exception as exc:
        print(f"Ошибка при выгрузке схемы: {exc}", file=sys.stderr)
        return 3

    print(f"Экспортировано {len(written)} объект(ов) в {args.output_dir}/", file=sys.stderr)
    for path in written:
        print(path)

    if errors:
        print(f"Не удалось выгрузить {len(errors)} объект(ов):", file=sys.stderr)
        for object_type, name, failure in errors:
            print(f"  {object_type} {name}: {failure}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
