# GAP-131: `NUMBER(p,s)` и `FLOAT` становятся двоичной плавающей точкой

Возможность Oracle: `NUMBER(p,s)` и `FLOAT` - десятичные типы. `0.1 + 0.2`
ровно `0.3`.

## Как найдено

Рядом с GAP-130, в таблице типов самого ora2pg (`Ora2Pg/Oracle.pm`,
`_sql_type`), затем запуском на Oracle 23ai и PostgreSQL 16.

## Минимальный пример

`tests/fixtures/silent_numbers/`, VALID в живом Oracle 23ai:

```sql
CREATE TABLE gx_pay (id NUMBER(10), amount NUMBER(10,2), rate NUMBER(5,4));

CREATE OR REPLACE FUNCTION gx_f1 RETURN VARCHAR2 IS
  a NUMBER(10,2) := 0.1;
  b NUMBER(10,2) := 0.2;
BEGIN
  IF a + b = 0.3 THEN RETURN 'equal'; END IF;
  RETURN 'not equal';
END;
/
CREATE OR REPLACE FUNCTION gx_f2 RETURN VARCHAR2 IS
  t NUMBER(12,2);
BEGIN
  SELECT SUM(amount) INTO t FROM gx_pay;
  RETURN TO_CHAR(t);
END;
/
```

## Вывод ora2pg (v25.0)

```sql
	amount double precision,
	rate decimal(5,4)
...
  a double precision := 0.1;
  b double precision := 0.2;
...
  t double precision;
```

С `PG_NUMERIC_TYPE 1` (ora2pg.conf из поставки) `NUMBER(p,s)` с
`0 < s <= p` становится `real` при `p <= 6` и `double precision` при
`p <= 15`; столбец с `p <= 6` получает `decimal(p,s)` (проверено:
столбцы `NUMBER(5,2)` и `NUMBER(6,2)` остаются decimal, `NUMBER(7,2)` и
`NUMBER(15,2)` становятся `double precision`, `NUMBER(16,2)` остаётся
decimal). `FLOAT` всегда становится `double precision`.

## Наблюдаемая проблема

Всё загружается в PostgreSQL 16, и при десяти строках с `amount = 0.1`:

| | Oracle 23ai | PostgreSQL 16 |
|---|---|---|
| `gx_f1()` | `equal` | `not equal` |
| `gx_f2()` (`SUM(amount)`) | `1` | `0.9999999999999999` |

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.** Деньги в
`double precision` - классическая ошибка, и здесь код её не просил.

Исправление - в ora2pg.conf, проверено на тех же файлах:

```
PG_NUMERIC_TYPE 0
DATA_TYPE       FLOAT:numeric
```

Тогда `NUMBER(p,s)` везде становится `decimal(p,s)`, а `FLOAT` -
`numeric`. Детектор сообщает один раз на файл, на первом таком
объявлении. `BINARY_FLOAT`/`BINARY_DOUBLE` и в Oracle двоичные (IEEE) и
не помечаются.

Реализовано: `ora2pg_gap_report/detectors/number_as_float.py`.
