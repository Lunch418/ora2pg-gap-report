# GAP-121: тип пакета в его собственных подпрограммах теряет имя пакета

Возможность Oracle: тип, объявленный в пакете - `SUBTYPE t_code IS
VARCHAR2(10)`, `TYPE pair_rt IS RECORD (...)`, `TYPE num_tt IS TABLE OF
NUMBER INDEX BY PLS_INTEGER`, - используется подпрограммами пакета без
имени пакета: параметр `p IN t_code`, переменная `r pair_rt;`, `RETURN
t_code`.

## Как найден

При сведении GAP-120 к минимальному случаю: после того как `%TYPE`
вписали руками, подпрограммы всё равно не загружались. `--load-check`
относил ошибки к недостающим зависимостям. У параметров `tab_param` в
OraOpenSource Logger та же форма.

## Минимальный пример

`tests/fixtures/gaps_120_123/calls_source.sql` (`gx_t_pkg`):

```sql
CREATE OR REPLACE PACKAGE gx_t_pkg AS
  SUBTYPE t_code IS VARCHAR2(10);
  TYPE pair_rt IS RECORD (a NUMBER(6), b VARCHAR2(10));
  TYPE num_tt IS TABLE OF NUMBER INDEX BY PLS_INTEGER;
  FUNCTION code_of(p IN t_code) RETURN t_code;
  FUNCTION pair_sum RETURN NUMBER;
  FUNCTION tab_count RETURN NUMBER;
END gx_t_pkg;
/
CREATE OR REPLACE PACKAGE BODY gx_t_pkg AS
  FUNCTION code_of(p IN t_code) RETURN t_code IS
    v t_code := p;
  BEGIN
    RETURN v || '!';
  END;
  FUNCTION pair_sum RETURN NUMBER IS
    r pair_rt;
  BEGIN
    r.a := 2;
    r.b := '3';
    RETURN r.a + TO_NUMBER(r.b);
  END;
  ...
END gx_t_pkg;
/
```

В живом Oracle 23ai: `code_of('ab')` - `ab!`, `pair_sum` - 5,
`tab_count` - 2.

## Вывод ora2pg (v25.0, `-t PACKAGE`)

```sql
CREATE DOMAIN gx_t_pkg.t_code AS varchar(10);
CREATE TYPE gx_t_pkg.pair_rt AS (
a integer, b varchar(10)
);
CREATE OR REPLACE FUNCTION gx_t_pkg.code_of (p t_code) RETURNS T_CODE AS $body$
DECLARE
    v t_code := p;
...
CREATE OR REPLACE FUNCTION gx_t_pkg.pair_sum () RETURNS bigint AS $body$
DECLARE
    r pair_rt;
```

Типы создаются в схеме пакета, а подпрограммы называют их без схемы.

## Наблюдаемая проблема

Схемы пакета нет в search_path, и PostgreSQL 16 отвергает каждую
подпрограмму, которая называет такой тип, хотя сами типы загрузились:

```
ERROR:  42704: type t_code does not exist
ERROR:  42704: type "pair_rt" does not exist
ERROR:  42704: type "num_tt" does not exist
```

Ссылка, написанная в Oracle с именем пакета (`gx_e_pkg.t_code`),
сохраняется как есть и загружается.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Допишите к
типу схему пакета (`gx_t_pkg.t_code`) или задайте функции `SET
search_path` с этой схемой. С именем схемы фикстура GAP-120 загружается и
возвращает то же, что Oracle (`tests/test_gaps_120_123_load.py`). У типа
`TABLE OF` поверх этого ещё GAP-003.

Тип REF CURSOR - это GAP-115. Тело, выгруженное без спецификации, типов
не объявляет, поэтому детектор знает только типы из того же файла;
каждый тип сообщается один раз.

Реализовано: `ora2pg_gap_report/detectors/package_type_reference.py`;
`--load-check` связывает `type "x" does not exist` с этим gap'ом, если тот
же файл создаёт `x` в схеме пакета.
