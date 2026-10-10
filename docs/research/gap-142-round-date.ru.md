# GAP-142: `ROUND` от даты

Возможность Oracle: `ROUND(d[, fmt])` округляет дату - до ближайшего дня или по формату, например `'MM'`.

## Как найдено

При проверке предыдущих пробелов: те же функции запускались в Oracle 23ai и, после ora2pg 25.0, в PostgreSQL 16.

## Минимальный пример

`tests/fixtures/char_to_char_round/oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE OR REPLACE FUNCTION gx_r4(d DATE) RETURN VARCHAR2 IS
BEGIN
  RETURN TO_CHAR(ROUND(d, 'MM'), 'YYYY-MM-DD') || '|' || TO_CHAR(ROUND(d), 'YYYY-MM-DD');
END;
/
```

## Вывод ora2pg (v25.0)

```sql
  RETURN TO_CHAR(ROUND(d, 'MM'), 'YYYY-MM-DD') || '|' || TO_CHAR(ROUND(d), 'YYYY-MM-DD');
```

ora2pg переписывает `TRUNC(d, 'MM')` в `date_trunc('month', d)` (проверено: `'MM'`, `'IW'`, `'Q'` переводятся верно), а `ROUND` копирует.

## Наблюдаемая проблема

Функция загружается; вызов падает (Oracle 23ai для 2026-03-17 15:00: `2026-04-01|2026-03-18`):

```
ERROR:  function round(timestamp without time zone, unknown) does not exist
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage runtime.** Перепишите через `date_trunc`: `date_trunc('day', d + interval '12 hours')` для дня; для месяца сравните день месяца с 16. Детектор помечает `ROUND` со строковым вторым аргументом (формат принимает только `ROUND` даты) и `ROUND` от переменной `DATE`/`TIMESTAMP` или `SYSDATE`.

Реализовано: `ora2pg_gap_report/detectors/round_date.py`.
