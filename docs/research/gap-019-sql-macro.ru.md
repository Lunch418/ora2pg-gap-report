# GAP-019: `SQL_MACRO` — функция-макрос конвертируется в обычную функцию

Oracle feature: `SQL_MACRO` (Oracle 20c+) — модификатор функции,
превращающий её в текстовый макрос, который Oracle подставляет прямо в
SQL-запрос на этапе разбора (`SQL_MACRO(SCALAR)` — как выражение,
`SQL_MACRO(TABLE)` — как табличное выражение), а не вызывает как обычную
функцию, возвращающую значение.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE BODY region_pkg AS
    FUNCTION in_top_region(p_region VARCHAR2) RETURN VARCHAR2 SQL_MACRO IS
    BEGIN
        RETURN 'region IN (''EU'', ''US'')';
    END;

    PROCEDURE count_top IS
        v_count NUMBER;
    BEGIN
        SELECT COUNT(*) INTO v_count
        FROM orders
        WHERE in_top_region(region);
    END count_top;
END region_pkg;
/
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

`SQL_MACRO` пропадает из сигнатуры функции без следа — функция
конвертируется в обычную PL/pgSQL-функцию, возвращающую `varchar`.
Вызывающий код (`WHERE in_top_region(region)`) копируется как есть — без
какой-либо подстановки текста макроса.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: сама функция компилируется без
ошибок. Падает вызывающая процедура при первом вызове:

```
ERROR:  argument of WHERE must be type boolean, not type character varying
LINE 2:         WHERE region_pkg_in_top_region(region)
                      ^
```

В Oracle `SQL_MACRO(SCALAR)`-функция, использованная в `WHERE`, на этапе
разбора подставляет туда свой текстовый результат как часть самого
запроса (`WHERE region IN ('EU', 'US')`) — работает как булево условие. В
PostgreSQL это просто вызов обычной функции, возвращающей `varchar`, и
PostgreSQL пытается использовать эту строку напрямую как `boolean` —
несовпадение типов.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/sql_macro.py`.
