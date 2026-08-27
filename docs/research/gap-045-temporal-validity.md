# GAP-045: `PERIOD FOR` — Temporal Validity, обрубок в выводе

Oracle feature: `PERIOD FOR <имя> (<начало>, <конец>)` (12c Temporal
Validity) — объявление периода действительности строки, дающее
возможность запрашивать состояние «как было на дату» через
`AS OF PERIOD FOR`.

## Минимальный пример

```sql
CREATE TABLE emp_hist (
    emp_id     NUMBER,
    valid_from DATE,
    valid_to   DATE,
    PERIOD FOR emp_valid_time (valid_from, valid_to)
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE emp_hist (
	emp_id bigint,
	valid_from timestamp(0),
	valid_to timestamp(0),
	period FOR
) ;
```

Это не отбрасывание секции и не копирование её целиком — в списке
столбцов остаётся **обрубок** `period FOR`, без имени периода и без
списка столбцов.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 — ломается создание всей таблицы,
а не только теряется фича:

```
ERROR:  syntax error at or near "FOR"
LINE 5:  period FOR
                ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/temporal_validity.py`. У PostgreSQL нет
встроенной temporal validity. Ручная переработка: обычная пара
timestamp-столбцов плюс фильтрация по ним в запросах, либо тип
`tstzrange` с ограничением-исключением, если нужен контроль пересечений
периодов.
