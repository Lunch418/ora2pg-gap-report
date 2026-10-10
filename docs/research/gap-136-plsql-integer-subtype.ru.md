# GAP-136: целые подтипы PL/SQL копируются как есть

Возможность Oracle: целые подтипы PL/SQL с ограничениями - `SIMPLE_INTEGER`, `NATURAL`, `NATURALN`, `POSITIVE`, `POSITIVEN`, `SIGNTYPE`.

## Как найдено

При проверке GAP-130..133: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/loud_types/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l4(n NUMBER) RETURN NUMBER IS
  s SIMPLE_INTEGER := 1;
  k NATURAL := 2;
  p POSITIVE := 3;
  g SIGNTYPE := -1;
BEGIN
  RETURN s + k + p + g + n;
END;
/
```

## Вывод ora2pg (v25.0, `-t FUNCTION`)

```sql
  s SIMPLE_INTEGER := 1;
  k NATURAL := 2;
  p POSITIVE := 3;
  g SIGNTYPE := -1;
```

`PLS_INTEGER` и `BINARY_INTEGER` становятся `integer`, а эти копируются.

## Наблюдаемая проблема

Функция не загружается:

```
ERROR:  type "simple_integer" does not exist
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Механически: `--fix` пишет в объявлениях `integer` (`smallint` для `SIGNTYPE`) (`fix_plsql_integer_subtypes`), и функция загружается и возвращает то же, что Oracle (`gx_l4(1)` = 6). Ограничение подтипа (не NULL, `> 0`, `>= 0`, -1..1) не переносится: добавьте проверку, где код на него полагается. Переменные спецификации пакета - это GAP-036, здесь они не помечаются.

Реализовано: `ora2pg_gap_report/detectors/plsql_integer_subtype.py`.
