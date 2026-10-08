# GAP-120: `%TYPE` в RECORD или SUBTYPE пакета копируется в DDL

Возможность Oracle: тип уровня пакета, привязанный к столбцу или
переменной - поле RECORD `salary gx_emp.salary%TYPE` или `SUBTYPE t_name
IS g_name_def%TYPE`, `SUBTYPE t_emp IS gx_emp%ROWTYPE`.

## Как найден

`--migrate --load-check docker` на примерах пакетов
(`docs/research/samples/`): четыре ошибки `syntax error at or near "%"`,
которые не объяснял ни один gap - `equitable_salaries_pkg.id_salary_rt`
(в `compound_trigger_dlee.sql`) и три подтипа `file_util_pkg` из
alexandria-plsql-utils. У `rec_logger_log` из OraOpenSource Logger та же
форма.

## Минимальный пример

`tests/fixtures/gaps_120_123/types_source.sql`:

```sql
CREATE TABLE gx_emp (emp_id NUMBER(6) PRIMARY KEY, salary NUMBER(8,2), name VARCHAR2(40));
CREATE OR REPLACE PACKAGE gx_rec_pkg AS
  TYPE emp_rt IS RECORD (
    emp_id gx_emp.emp_id%TYPE,
    salary gx_emp.salary%TYPE
  );
  g_name_def VARCHAR2(40);
  SUBTYPE t_name IS g_name_def%TYPE;
  SUBTYPE t_sal IS gx_emp.salary%TYPE;
  FUNCTION top_salary RETURN NUMBER;
  FUNCTION label(p IN t_name) RETURN t_name;
END gx_rec_pkg;
/
```

и тело, которое использует оба (полный файл - в фикстуре). В живом
Oracle 23ai пакет VALID, `top_salary` возвращает 200, `label('x')` -
`<x>`.

## Вывод ora2pg (v25.0, `-t PACKAGE`)

```sql
CREATE TYPE gx_rec_pkg.emp_rt AS (
emp_id gx_emp.emp_id%TYPE,
    salary gx_emp.salary%TYPE
);
CREATE DOMAIN gx_rec_pkg.t_name AS g_name_def%TYPE;
CREATE DOMAIN gx_rec_pkg.t_sal AS gx_emp.salary%TYPE;
```

`%ROWTYPE` копируется так же: `CREATE DOMAIN gx_e_pkg.t_emp AS
gx_emp%ROWTYPE`, `e gx_emp%ROWTYPE` внутри CREATE TYPE.

## Наблюдаемая проблема

`%TYPE` - синтаксис объявлений PL/pgSQL, в SQL DDL его нет, поэтому
PostgreSQL 16 отвергает все три команды:

```
ERROR:  42601: syntax error at or near "%"
```

а за ними падают все подпрограммы, которые используют эти типы.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Впишите на
место привязки тип столбца или переменной (`numeric(8,2)`,
`varchar(40)`); для `%ROWTYPE` - строковый тип самой таблицы (`gx_emp`).
Так написанная фикстура загружается и ведёт себя как в Oracle
(`tests/test_gaps_120_123_load.py`).

Только объявления уровня пакета: тип, объявленный внутри подпрограммы,
остаётся объявлением PL/pgSQL, где `%TYPE` допустим.

Реализовано: `ora2pg_gap_report/detectors/package_type_anchor.py`;
`--load-check` узнаёт скопированную привязку в `CREATE TYPE`/`CREATE
DOMAIN`.
