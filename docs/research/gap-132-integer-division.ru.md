# GAP-132: деление целых отбрасывает дробную часть

Возможность Oracle: `/` всегда возвращает NUMBER. `7 / 2` = `3.5`, как бы
ни были объявлены операнды.

## Как найдено

Вместе с GAP-130: `NUMBER(10) / NUMBER(10)` и `PLS_INTEGER / 2` дали
разные результаты в Oracle 23ai и PostgreSQL 16.

## Минимальный пример

`tests/fixtures/silent_numbers/oracle_functions.sql`, VALID в живом
Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_d1(n NUMBER) RETURN VARCHAR2 IS
  b NUMBER(9,0) := n;
  e BINARY_INTEGER := n;
BEGIN
  RETURN (7 / 2) || '|' || ROUND(b / 2) || '|' || (e / 2);
END;
/
```

## Вывод ora2pg (v25.0)

```sql
  b integer := n;
  e integer := n;
BEGIN
  RETURN(7 / 2) || '|' || ROUND(b / 2) || '|' || (e / 2);
```

`NUMBER(p)` и `NUMBER(p,0)` становятся `smallint`, `integer` или
`bigint` (p <= 19), `INTEGER`, `PLS_INTEGER`, `BINARY_INTEGER` -
`integer`; деление копируется.

## Наблюдаемая проблема

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_d1(7)` | `3.5\|4\|3.5` | `3\|3\|3` |
| `-7 / 2` | -3.5 | -3 |

Найдено в OraOpenSource Logger, `docs/research/samples/logger.pkb`:
`p_date_stop - p_date_start < 1/1440` - минута в долях суток в Oracle и 0
в PostgreSQL.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.** Приведите
одну сторону: `i::numeric / 2`.

Детектор помечает `a / b`, где каждая сторона - целый литерал или
переменная/параметр одного из типов выше в той же подпрограмме или её
пакете. Не помечаются: `NUMBER` без точности (это GAP-130, и с его
исправлением проблема уходит), `TRUNC(a / b)` (результат тот же), `2.0` и
столбцы, типов которых подпрограмма не показывает.

Реализовано: `ora2pg_gap_report/detectors/integer_division.py`.
