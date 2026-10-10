# GAP-140: `TO_CHAR` даты или дроби без формата

Возможность Oracle: `TO_CHAR(x)` без формата форматирует дату по `NLS_DATE_FORMAT` сессии (`17-MAR-26` по умолчанию), а число - без ведущего нуля (`.5`).

## Как найдено

При проверке предыдущих пробелов: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_r2(n NUMBER) RETURN VARCHAR2 IS
  v NUMBER(5,2) := 0.5;
  d DATE := DATE '2026-03-17';
BEGIN
  RETURN TO_CHAR(v) || '|' || TO_CHAR(d);
END;
/
```

## Вывод ora2pg (v25.0)

```sql
  v real := 0.5;
  d timestamp(0) := timestamp(0) '2026-03-17';
BEGIN
  RETURN v::text || '|' || d::text;
```

`TO_CHAR(x)` становится `x::text`, и PostgreSQL пишет значение по-своему.

## Наблюдаемая проблема

Всё загружается и выполняется, но возвращает другой текст:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_r2(1)` | `.5\|17-MAR-26` | `0.5\|2026-03-17 00:00:00` |

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.** Укажите формат явно, в Oracle или после конвертации: `to_char(d, 'DD-MON-YY')`. Детектор помечает `TO_CHAR` с одним аргументом от переменной или параметра `DATE` или `TIMESTAMP`, от `SYSDATE`/`SYSTIMESTAMP`, от переменной, которая становится `real`, `double precision` или `decimal`, и от дробного литерала. Целое пишется одинаково и не помечается; тип столбца неизвестен.

Реализовано: `ora2pg_gap_report/detectors/to_char_default_format.py`.
