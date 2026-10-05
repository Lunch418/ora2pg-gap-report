# GAP-114: константа пакета из другой константы - выражение склеивается

Oracle feature: константа (или переменная) уровня пакета, начальное
значение которой вычисляется из другой константы того же пакета.

## Как нашли

Не из гипотезы: `--load-check` на настоящем выводе ora2pg для пакета
OraOpenSource Logger (`docs/research/samples/logger.pkb`) показал две
функции, падающие на синтаксической ошибке, которую не объяснял ни один
пробел реестра. В Logger объявлено

```sql
gc_date_format constant varchar2(255) := 'DD-MON-YYYY HH24:MI:SS';
gc_timestamp_format constant varchar2(255) := gc_date_format || ':FF';
```

и падали как раз функции, читающие `gc_timestamp_format`.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE BODY fmt_pkg AS
  c_date CONSTANT VARCHAR2(30) := 'YYYY-MM-DD';
  c_stamp CONSTANT VARCHAR2(30) := c_date || ' HH24:MI';

  FUNCTION stamp_fmt RETURN VARCHAR2 IS
  BEGIN
    RETURN c_stamp;
  END;
END fmt_pkg;
/
```

В живом Oracle 23ai пакет компилируется, а `fmt_pkg.stamp_fmt` возвращает
`YYYY-MM-DD HH24:MI`.

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Из исходника, написанного вручную:

```sql
CREATE OR REPLACE FUNCTION fmt_pkg.stamp_fmt () RETURNS varchar AS $body$
BEGIN
    RETURN current_setting('fmt_pkg.c_stamp')::varchar(30)current_setting('fmt_pkg.c_date')::varchar(30)||;
  END;
$body$
LANGUAGE PLPGSQL
```

Из того же пакета, выгруженного через `DBMS_METADATA.GET_DDL`:

```sql
    RETURN current_setting('fmt_pkg.c_stamp')::varchar(30)c_date||;
```

ora2pg переписывает каждое чтение переменной пакета в `current_setting()`
(эмуляция из GAP-036). Для константы, в инициализаторе которой названа
другая константа, он дописывает куски инициализатора после первой ссылки,
а `||` остаётся висеть в конце.

## Наблюдаемая проблема

Функция не загружается в PostgreSQL 16:

```
ERROR:  42601: syntax error at or near "("
```

Так же падает каждая подпрограмма, читающая константу. Константы с
литералом в инициализаторе этот пробел не касается (у неё остаётся
проблема GAP-036: значение никто не задаёт).

**Воспроизводится: ДА.** Ora2Pg 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Замените
константу функцией `IMMUTABLE`, возвращающей готовое значение (см.
[рецепт про состояние пакета](../recipes/package-state.ru.md)), или
вычисляйте значение там, где оно используется.

Реализовано: `ora2pg_gap_report/detectors/package_constant_chain.py` -
читает собственную секцию объявлений пакета (спецификации или тела) и
отмечает объявление, в инициализаторе которого названо более раннее.
