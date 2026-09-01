# GAP-092: `IF` не дописывается до формы PL/pgSQL

MSSQL feature: `IF` — условный оператор T-SQL, в двух формах: с блоком `BEGIN ... END` и без него.

## Минимальный пример

```sql
CREATE PROCEDURE dbo.if_blk @x int AS
BEGIN
    IF @x < 0
    BEGIN
        INSERT INTO orders (nm) VALUES ('neg');
    END
END;
```

## Вывод ora2pg (v25.0, `-M -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE dbo.if_blk (p_x integer) AS $body$
BEGIN
BEGIN 
     IF  p_x < 0 THEN
        INSERT INTO orders(nm) VALUES ('neg');
    END
END;
END;
$body$
```

Слово `THEN` подставлено правильно, а вот закрывающее `END` так и
осталось `END` вместо `END IF`.

## Наблюдаемая проблема

Загрузка проходит чисто — ora2pg выставляет в своём выводе
`check_function_bodies = false`, поэтому тело не разбирается. При
разборе тела на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "END"
```

Вторая форма, без блока, ломается иначе — там не подставляется и `THEN`:

```sql
CREATE PROCEDURE dbo.if_nb @x int AS
BEGIN
    IF @x < 0
        INSERT INTO orders (nm) VALUES ('neg');
END;
```

```
ERROR:  missing "THEN" at end of SQL expression
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MSSQL (`ora2pg -M`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Обе формы
сломаны, но по-разному, поэтому детектор намеренно не пытается их
различать: правится всё равно одинаково — переписыванием в полную форму
PL/pgSQL, `IF <условие> THEN <операторы>; END IF;`. Реализовано:
`ora2pg_gap_report/detectors/mssql_if_statement.py`.
