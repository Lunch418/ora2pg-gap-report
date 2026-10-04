*[English](README.md) | Русский*

# Рецепты миграции

[Исследования](../research/GAP_REGISTRY.md) говорят, что `ora2pg` делает не
так и откуда это известно. Рецепт говорит, что писать вместо этого: для
класса проблем - приём в PostgreSQL с кодом, который работает.

| Рецепт | Пробелы |
|---|---|
| [Иерархические запросы: CONNECT BY -> WITH RECURSIVE](hierarchical-queries.ru.md) | GAP-005, 014, 024, 039 |
| [Коллекции и массовые операции](collections-and-bulk.ru.md) | GAP-003, 021, 041, 054 |
| [Автономные транзакции](autonomous-transactions.ru.md) | GAP-001 |
| [Переменные пакета и контексты приложения](package-state.ru.md) | GAP-015, 036 |
| [Глобальные временные таблицы](temporary-tables.ru.md) | GAP-012, 111 |
| [PIVOT и UNPIVOT](pivot-unpivot.ru.md) | GAP-008 |
| [INSERT ALL, MERGE ... DELETE и upsert](multi-table-dml.ru.md) | GAP-002, 016, 070, 076, 077 |
| [Ошибки: как бросать, ловить и называть](error-handling.ru.md) | GAP-060, 071, 084, 093, 094 |
| [Database link -> postgres_fdw](database-links.ru.md) | GAP-006 |
| [Вызовы DBMS_* и UTL_*](builtin-packages.ru.md) | `dbms_utl_calls` |
| [KEEP, IGNORE NULLS, WM_CONCAT и SAMPLE](analytic-functions.ru.md) | GAP-040, 042, 048, 065 |
| [Таблицы и представления только для чтения, невидимые столбцы и индексы](read-only-and-invisible.ru.md) | GAP-020, 025, 026, 066 |
| [Секционированные таблицы](partitioning.ru.md) | GAP-013 |
| [Выражения T-SQL](tsql-expressions.ru.md) | GAP-095, 096, 097, 098, 099 |
| [Выражения MySQL](mysql-expressions.ru.md) | GAP-068, 069, 075, 079, 081, 086 |

`ora2pg-gap-report --explain GAP-NNN` и отчёты ссылаются на рецепт для
каждого пробела, у которого он есть.

## Как проверяется код

Каждый блок ` ```sql ` в рецепте - это PostgreSQL, который выполняется как
написан. `tests/test_recipes.py` по порядку загружает блоки каждой
страницы в настоящий PostgreSQL 16 через `--load-check`, а блоки
`DO ... ASSERT` на страницах проверяют, что каждый приём делает то, что
написано. Если рецепт перестаёт работать, сборка падает. Код, который
только показывается, например исходник Oracle или команда, которой нужна
вторая база, оформлен как ` ```plsql ` или ` ```pgsql ` и не выполняется.

Рецепт для класса, которого здесь нет, будет кстати: та же структура
(проблема, приём, что не переносится) и код, который проходит тест. См.
[CONTRIBUTING](../../CONTRIBUTING.ru.md).
