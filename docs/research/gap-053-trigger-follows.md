# GAP-053: `FOLLOWS` / `PRECEDES` — порядок срабатывания триггеров

Oracle feature: оговорка, задающая порядок срабатывания триггеров на
одном и том же событии одной таблицы.

## Минимальный пример

```sql
CREATE OR REPLACE TRIGGER trg_b
BEFORE INSERT ON employees
FOR EACH ROW
FOLLOWS trg_a
BEGIN
  :NEW.audited := 'Y';
END;
/
```

## Вывод ora2pg (v25.0, `-t TRIGGER`)

```sql
CREATE OR REPLACE FUNCTION trigger_fct_trg_b() RETURNS trigger AS $BODY$
FOLLOWS trg_a
BEGIN
  NEW.audited := 'Y';
RETURN NEW;
END
$BODY$
 LANGUAGE 'plpgsql';
CREATE TRIGGER trg_b
	BEFORE INSERT ON employees FOR EACH ROW
	EXECUTE PROCEDURE trigger_fct_trg_b();
```

Ключевое: оговорка не отброшена, а попала **внутрь тела функции** —
между `AS $BODY$` и `BEGIN`.

## Наблюдаемая проблема

Загрузка проходит полностью чисто (ora2pg выставляет в своём выводе
`check_function_bodies = false`, поэтому тело не разбирается):

```
DROP TRIGGER
CREATE FUNCTION
CREATE TRIGGER
```

Падение происходит при первом же `INSERT` в таблицу. Подтверждено на
реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "FOLLOWS"
LINE 2: FOLLOWS trg_a
        ^
QUERY:
FOLLOWS trg_a
BEGIN
```

То есть ломается не порядок срабатывания триггеров, а вообще любая
операция вставки в таблицу — это `failure_stage = runtime`, а не
`deployment`, и проверено это именно так, а не выведено по аналогии.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/trigger_follows.py`. Детектор ищет
оговорку только в заголовке триггера (от `CREATE TRIGGER` до первого
`DECLARE`/`BEGIN`/`CALL`) — там, где её и разрешает грамматика Oracle:
`FOLLOWS` само по себе вполне обычный идентификатор (`SELECT follows
FROM t`), и без этого ограничения детектор давал бы ложные срабатывания.

Ручная переработка: в PostgreSQL порядка «по имени предшественника» нет
— триггеры на одном событии срабатывают в алфавитном порядке имён.
Оговорку нужно убрать, а нужную последовательность обеспечить
именованием (`t10_...`, `t20_...`) или слиянием триггеров в один.
