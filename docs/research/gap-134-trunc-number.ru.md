# GAP-134: `TRUNC` от числа становится `date_trunc`

Возможность Oracle: `TRUNC` принимает дату или число. `TRUNC(10 / 3)` = 3, `TRUNC(3.14159, 2)` = 3.14.

## Как найдено

При проверке GAP-130..133: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/loud_types/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l1(n NUMBER) RETURN NUMBER IS
BEGIN
  RETURN TRUNC(n / 3);
END;
/
CREATE OR REPLACE FUNCTION gx_l2(n NUMBER) RETURN NUMBER IS
BEGIN
  RETURN TRUNC(n, 2);
END;
/
```

## Вывод ora2pg (v25.0, `-t FUNCTION`)

```sql
  RETURN date_trunc('day', n / 3);
...
  RETURN date_trunc(2, n);
```

ora2pg переписывает любой `TRUNC` как TRUNC даты, каков бы ни был аргумент: `TRUNC(n)`, `TRUNC(ABS(n))`, `TRUNC(TO_NUMBER(s))` - всё становится `date_trunc('day', ...)`.

## Наблюдаемая проблема

Обе функции загружаются, и первый же вызов падает:

```
ERROR:  function date_trunc(unknown, bigint) does not exist
```

Найдено в OraOpenSource Logger: `trunc((p_date_stop-p_date_start)/7) || ' weeks'`.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage runtime.** Замените `date_trunc` на `trunc`. Детектор помечает `TRUNC`, у которого аргумент явно число: числовой литерал, числовая переменная или параметр, числовая функция (`TO_NUMBER`, `ABS`, `ROUND`, ...), выражение с `*` или `/`, или второй аргумент-число - у даты это строка формата. `TRUNC` от столбца не отличить, он не помечается.

Реализовано: `ora2pg_gap_report/detectors/trunc_number.py`.
