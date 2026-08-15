# Changelog

Формат по мотивам [Keep a Changelog](https://keepachangelog.com/ru/1.0.0/).
Проект следует [SemVer](https://semver.org/lang/ru/) в упрощённом виде,
пока не достигнет 1.0.0: minor-версия — новые детекторы/возможности,
patch — исправления в существующих.

## [Unreleased]

С момента релиза 0.2.0 в `main` смёржено ощутимо больше, чем отражает
текущий номер версии в `pyproject.toml` — следующий релиз назрел.

### Added
- 14 новых детекторов, GAP-008…GAP-021: `pivot_clause`, `object_type`,
  `with_function`, `flashback_query`, `global_temp_table`,
  `table_partitioning`, `connect_by_nocycle`, `context_object`,
  `insert_all`, `json_table`, `external_table`, `sql_macro`,
  `invisible_column`, `collection_type`. Реестр — теперь 21 подтверждённый
  gap, см. `docs/research/GAP_REGISTRY.md`.
- Полностью переработанный терминальный вывод (`rich`): баннер,
  сводная панель, дерево «объекты с наибольшим числом находок»,
  секция рекомендаций по каждому сработавшему детектору, панель оценки
  трудозатрат (лучший/среднее/худший случай).
- Флаги `--severity` и `--object` для фильтрации находок в отчёте.
- Флаг `--version`.
- Поддержка директорий в качестве аргумента — рекурсивный поиск
  `.sql`/`.pks`/`.pkb` файлов, не только явный список файлов.
- `docs/research/GAP_REGISTRY.md` — формализованный реестр gap'ов с
  версией ora2pg, на которой каждый подтверждён, и статусом
  (`confirmed`/`fixed-upstream`/`wont-fix`).

## [0.2.0] - 2026-08-14

### Added
- GAP-002 `merge_delete_clause` — `MERGE ... DELETE WHERE`.
- GAP-003 `bulk_collect` — `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` /
  `FORALL`.
- GAP-006 `database_link` — `table@dblink_name`.
- GAP-007 `model_clause` — `MODEL PARTITION BY ... MEASURES ... RULES`.
- PyPI-бейдж в README.

## [0.1.0] - 2026-08-14

Первый релиз.

### Added
- GAP-001 `autonomous_tx` — `PRAGMA AUTONOMOUS_TRANSACTION`, недооценка
  стоимости в `SHOW_REPORT`/`--estimate_cost`.
- GAP-004 `compound_triggers` — `COMPOUND TRIGGER`, тихий провал
  файлового парсера ora2pg.
- GAP-005 `connect_by` — баг подстановки `LEVEL` в сгенерированном
  `WITH RECURSIVE` (опционально, `--check-connect-by`, требует ora2pg).
- `dbms_utl_calls` — классификатор конкретных вызовов `DBMS_*`/`UTL_*`.
- CLI: `--format` (terminal/markdown/json), `--output`.
- Выгрузка DDL напрямую из Oracle: `ora2pg-gap-export`.
