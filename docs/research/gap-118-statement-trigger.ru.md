# GAP-118: триггер уровня команды становится `FOR EACH ROW`

Oracle feature: DML-триггер без `FOR EACH ROW` - триггер уровня команды,
который срабатывает один раз на команду, сколько бы строк она ни
затронула. Им пересчитывают сводки, журналируют пакет изменений,
проверяют правило по всей таблице после изменения.

## Как нашли

При проверке вывода триггеров для GAP-117: минимальный триггер уровня
команды вышел с `FOR EACH ROW`.

## Минимальный пример

```sql
CREATE OR REPLACE TRIGGER gx_t_ai AFTER INSERT ON gx_orders
BEGIN
  UPDATE gx_fired SET n = n + 1;
END;
/
```

В живом Oracle 23ai `INSERT INTO gx_orders SELECT level FROM dual CONNECT
BY level <= 5` вставляет пять строк, а триггер выполняется один раз:
`gx_fired.n` равен 1.

## Вывод ora2pg (v25.0, `-t TRIGGER`)

Одинаковый для исходника, написанного вручную, и для
`DBMS_METADATA.GET_DDL` (`CREATE OR REPLACE EDITIONABLE TRIGGER
"HR"."GX_T_AI" AFTER INSERT ON gx_orders ...`):

```sql
CREATE OR REPLACE FUNCTION trigger_fct_gx_t_ai() RETURNS trigger AS $BODY$
BEGIN
  UPDATE gx_fired SET n = n + 1;
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
CREATE TRIGGER gx_t_ai
	AFTER INSERT ON gx_orders FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_gx_t_ai();
```

## Наблюдаемая проблема

В PostgreSQL 16 всё загружается. Та же вставка пяти строк выполняет
триггер пять раз: `gx_fired.n` равен 5. Проверено через `--load-check`,
где `ASSERT (SELECT n FROM gx_fired) = 1` после вставки не выполняется.
Никакой ошибки нет; всё, что триггер считает, журналирует или
пересчитывает, умножается на число строк, а триггер, пересчитывающий всю
таблицу, теперь делает это на каждую строку.

**Воспроизводится: ДА.** Ora2Pg 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage semantic.** В
сгенерированном триггере замените `FOR EACH ROW` на `FOR EACH STATEMENT`,
а в его функции `RETURN NEW` на `RETURN NULL` (у триггера уровня команды
нет строки). Не отмечаются: триггеры `INSTEAD OF` (по определению уровня
строки), составные триггеры (GAP-004), триггеры на `SCHEMA`/`DATABASE`
(GAP-052).

Реализовано: `ora2pg_gap_report/detectors/statement_trigger.py`.
