# GAP-135: `FLOAT(n)` в PL/SQL становится `double precision(n)`

Возможность Oracle: `FLOAT(n)`, подтип NUMBER с двоичной точностью, в объявлении PL/SQL.

## Как найдено

При проверке GAP-130..133: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/loud_types/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l3(n NUMBER) RETURN NUMBER IS
  f FLOAT(10) := n;
BEGIN
  RETURN f * 2;
END;
/
```

## Вывод ora2pg (v25.0, `-t FUNCTION`)

```sql
  f double precision(10) := n;
```

Столбец `FLOAT(10)` становится просто `double precision`; в PL/SQL точность остаётся.

## Наблюдаемая проблема

Функция не загружается:

```
ERROR:  syntax error at or near "("
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Механически: `--fix` убирает точность (`fix_double_precision_length` в `ora2pg_gap_report/autofix.py`), и функция загружается и возвращает то же, что Oracle (`gx_l3(2)` = 4). `--load-check` показывает эту ошибку как исправимую.

Реализовано: `ora2pg_gap_report/detectors/float_precision.py`.
