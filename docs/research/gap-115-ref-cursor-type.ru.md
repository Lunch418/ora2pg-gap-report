# GAP-115: `TYPE ... IS REF CURSOR` становится невалидным `CREATE TYPE ... AS REFCURSOR`

Oracle feature: именованный тип курсорной переменной, слабый (`IS REF
CURSOR`) или сильный (`IS REF CURSOR RETURN rowtype`), объявленный в пакете
или подпрограмме и используемый для параметров, возвращаемых значений и
переменных.

## Как нашли

`--load-check` на выводе ora2pg для
`docs/research/samples/connect_by_hierarchy_pkg.sql`, где в спецификации
объявлено `TYPE refcursor IS REF CURSOR;`: первая же команда
сконвертированного пакета не загрузилась.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE emp_api AS
  TYPE emp_cur IS REF CURSOR;
  TYPE emp_strong_cur IS REF CURSOR RETURN employees%ROWTYPE;
  FUNCTION list_all RETURN emp_cur;
END emp_api;
/
CREATE OR REPLACE PACKAGE BODY emp_api AS
  FUNCTION list_all RETURN emp_cur IS
    c emp_cur;
  BEGIN
    OPEN c FOR SELECT * FROM employees;
    RETURN c;
  END;
END emp_api;
/
```

В живом Oracle 23ai обе части компилируются, и вызывающий код читает
строки из `emp_api.list_all`.

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Одинаковый для исходника, написанного вручную, и для
`DBMS_METADATA.GET_DDL`:

```sql
CREATE OR REPLACE TYPE emp_api.emp_cur AS REFCURSOR;
CREATE OR REPLACE TYPE emp_api.emp_strong_cur AS REFCURSOR RETURN employees%ROWTYPE;
CREATE OR REPLACE FUNCTION emp_api.list_all () RETURNS EMP_CUR AS $body$
DECLARE
    c emp_cur;
BEGIN
    OPEN c FOR SELECT * FROM employees;
    RETURN c;
  END;
$body$
```

## Наблюдаемая проблема

В PostgreSQL 16 нет `CREATE OR REPLACE TYPE`, а `refcursor` - один
встроенный тип без именованных вариантов, поэтому ни одна из команд
создания типа не загружается:

```
ERROR:  42601: syntax error at or near "TYPE"
```

как и любая функция, где тип назван:

```
ERROR:  42704: type "emp_cur" does not exist
```

**Воспроизводится: ДА.** Ora2Pg 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Удалите
команды создания типов и пишите `refcursor` везде, где назван тип.
Сильный курсор теряет проверку типа строки при компиляции; строки он
возвращает те же. `SYS_REFCURSOR` это не затрагивает: ora2pg переводит его
в `refcursor`.

Реализовано: `ora2pg_gap_report/detectors/ref_cursor_type.py`.
