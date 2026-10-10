# GAP-138: арифметика с переменной `DATE`

Возможность Oracle: `дата + n` - дата через n дней (n может быть дробным, `1/24` - час), а `дата - дата` - число дней.

## Как найдено

При проверке GAP-130..133: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/loud_types/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_l6(d1 DATE, d2 DATE) RETURN NUMBER IS
  days NUMBER;
BEGIN
  days := d1 - d2;
  RETURN days;
END;
/
CREATE OR REPLACE FUNCTION gx_l7(d DATE) RETURN VARCHAR2 IS
  nxt DATE := d + 1;
BEGIN
  RETURN TO_CHAR(nxt, 'YYYY-MM-DD') || '|' || TO_CHAR(TRUNC(d) - 7, 'YYYY-MM-DD');
END;
/
```

## Вывод ora2pg (v25.0, `-t FUNCTION`)

```sql
  days := d1 - d2;
...
  nxt timestamp(0) := d + 1;
...
  RETURN TO_CHAR(nxt, 'YYYY-MM-DD') || '|' || TO_CHAR(date_trunc('day', d) - 7, 'YYYY-MM-DD');
```

`DATE` становится `timestamp(0)`. `SYSDATE + 1` переписывается в `clock_timestamp() + interval '1 days'`, а арифметика с переменной или параметром копируется.

## Наблюдаемая проблема

Обе загружаются и падают при вызове (Oracle 23ai: `gx_l6` = 2, `gx_l7` = `2026-01-11|2026-01-03`):

```
ERROR:  invalid input syntax for type bigint: "2 days"
ERROR:  operator does not exist: timestamp without time zone + integer
```

Найдено в OraOpenSource Logger: одиннадцать `p_date_stop-p_date_start` в `date_text_format_base`.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage runtime.** Пишите `d + interval '1 day'` и `extract(epoch from (d1 - d2)) / 86400`. Детектор знает переменные и параметры `DATE` или `TIMESTAMP` той же подпрограммы или её пакета и помечает прибавление или вычитание числа, `TRUNC` от них или от `SYSDATE` с числом и разность двух `DATE` (`TIMESTAMP - TIMESTAMP` и в Oracle даёт interval). Тип столбца неизвестен.

Реализовано: `ora2pg_gap_report/detectors/date_arithmetic.py`.
