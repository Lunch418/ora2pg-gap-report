# GAP-145: `TRIM(LEADING ... FROM ...)` становится `trim(both leading ...)`

Возможность Oracle: `TRIM(LEADING x FROM y)`, `TRIM(TRAILING x FROM y)` - тот же синтаксис, что и в PostgreSQL.

## Как найдено

Прогон --migrate --load-check на чужом коде (utPLSQL, OraOpenSource Logger, библиотека Alexandria PL/SQL, демо-схемы Oracle) и разбор ошибок, которые не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/corpus_gaps/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
  RETURN trim(leading a_c from a_item) || '|' || trim(trailing a_c from a_item) || '|' || a_base;
```

## Вывод ora2pg (v25.0)

```sql
  RETURN trim(both leading a_c from a_item) || '|' || trim(both trailing a_c from a_item) || '|' || a_base;
```

ora2pg ставит BOTH перед каждым TRIM, в том числе перед уже стоящими LEADING или TRAILING. `TRIM(BOTH ...)` и `TRIM(x)` переводятся верно.

## Наблюдаемая проблема

Подпрограмма не загружается:

```
ERROR:  syntax error at or near "leading"
```

Найдено в utPLSQL: `trim(leading a_connector from a_item)` в `ut_utils`.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Механически: `--fix` убирает лишний BOTH (`fix_trim_both_side`), проверено: `gx_c1('..ab..')` возвращает `ab..|..ab|0`, как в Oracle.

Реализовано: `ora2pg_gap_report/detectors/trim_leading_trailing.py`.
