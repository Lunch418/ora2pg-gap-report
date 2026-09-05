# GAP-011: `AS OF TIMESTAMP`/`AS OF SCN` — flashback-запрос

Oracle feature: `SELECT ... FROM table AS OF TIMESTAMP (...)` / `AS OF SCN
...` — чтение таблицы такой, какой она была в прошлом (использует
undo-данные Oracle), без отдельной таблицы истории.

## Минимальный пример

```sql
SELECT COUNT(*) INTO v_count
FROM orders AS OF TIMESTAMP (SYSTIMESTAMP - INTERVAL '1' DAY)
WHERE status = 'OPEN';
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Конструкция копируется как есть, но с побочным искажением текста при
подстановке `SYSTIMESTAMP` → `statement_timestamp()`: в выводе получилось
`AS OF timestamp(tatement_timestamp() - INTERVAL '1' DAY)` — потеряна
буква `s` в начале `statement_timestamp` (похоже на артефакт коллизии
между заменой `SYSTIMESTAMP` и приведением `TIMESTAMP` из `AS OF
TIMESTAMP` к нижнему регистру). Не проверялось на других вариантах
временного выражения — возможно, специфично для этого конкретного случая.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` проходит без
ошибки, падает при первом вызове:

```
ERROR:  syntax error at or near "timestamp"
```

Но даже без искажения текста результат был бы невалиден — в PostgreSQL
нет встроенного эквивалента flashback-запроса вообще. Нужен отдельный
архитектурный механизм — temporal tables через расширение или собственные
таблицы истории/аудита, а не синтаксическая замена.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/flashback_query.py`.
