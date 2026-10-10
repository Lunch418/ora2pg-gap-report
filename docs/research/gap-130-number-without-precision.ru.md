# GAP-130: `NUMBER` без точности становится `bigint`

Возможность Oracle: `NUMBER` без точности хранит любое десятичное значение
- в столбце, переменной, параметре или типе результата.

## Как найдено

Поиск того, что загружается, а потом считает иначе (после GAP-129): одни
и те же функции запускались в Oracle 23ai и, после ora2pg, в PostgreSQL 16,
результаты сравнивались.

## Минимальный пример

`tests/fixtures/silent_numbers/oracle_tables.sql` и
`oracle_functions.sql`, VALID в живом Oracle 23ai:

```sql
CREATE TABLE gx_prices (id NUMBER, price NUMBER, qty NUMBER(5));

CREATE OR REPLACE FUNCTION gx_n1 RETURN NUMBER IS
  v NUMBER := 2.5;
BEGIN
  RETURN v * 2;
END;
/
CREATE OR REPLACE FUNCTION gx_n2(p NUMBER) RETURN NUMBER IS
BEGIN
  RETURN p / 4;
END;
/
```

## Вывод ora2pg (v25.0, `-t TABLE`, `-t FUNCTION`)

```sql
CREATE TABLE gx_prices (
	id bigint,
	price bigint,
	qty integer
) ;
CREATE OR REPLACE FUNCTION gx_n1 () RETURNS bigint AS $body$
DECLARE
  v bigint := 2.5;
...
CREATE OR REPLACE FUNCTION gx_n2 (p bigint) RETURNS bigint AS $body$
```

В ora2pg.conf, который поставляется с ora2pg, стоят `PG_INTEGER_TYPE 1` и
`DEFAULT_NUMERIC bigint`: `NUMBER` без точности становится
`DEFAULT_NUMERIC` (`Ora2Pg/Oracle.pm`, `_sql_type`).

## Наблюдаемая проблема

Всё загружается в PostgreSQL 16 без ошибок, а затем:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| в `price` записаны 9.99 и 0.25, `SUM(price)` | 10.24 | 10 (записаны 10 и 0) |
| `gx_n1()` (`v := 2.5; RETURN v * 2`) | 5 | 6 |
| `gx_n2(10)` (`p / 4`) | 2.5 | 2 |

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.**

Исправление - одна строка в ora2pg.conf, проверено на тех же файлах:

```
DEFAULT_NUMERIC numeric
```

и каждый `NUMBER` выше становится `numeric`. Поэтому детектор сообщает
один раз на файл, на первом `NUMBER` без точности, а не на каждый
столбец: работа - это настройка, а не каждое объявление. `NUMBER(p)`,
`NUMBER(p,s)`, `TO_NUMBER`, `%TYPE` и `CAST(x AS NUMBER)` не помечаются.

`--migrate` по умолчанию конвертирует с этими настройками (см. README, `--migrate`).

Реализовано: `ora2pg_gap_report/detectors/number_without_precision.py`
(объявления читает `ora2pg_gap_report/number_types.py`).
