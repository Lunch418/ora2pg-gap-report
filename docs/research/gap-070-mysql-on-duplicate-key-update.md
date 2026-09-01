# GAP-070: `INSERT ... ON DUPLICATE KEY UPDATE`

MySQL/MariaDB feature: `ON DUPLICATE KEY UPDATE` — upsert-конструкция:
если вставка конфликтует с уникальным ключом/`PRIMARY KEY`, обновить
существующую строку вместо ошибки.

## Минимальный пример

```sql
CREATE TABLE counters (
  id INT PRIMARY KEY,
  hits INT NOT NULL DEFAULT 0
);

CREATE PROCEDURE bump(IN p_id INT)
BEGIN
  INSERT INTO counters (id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1;
END;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE bump (IN p_id integer) AS $body$
BEGIN
  INSERT INTO counters(id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1;
END;
$body$
LANGUAGE PLPGSQL
;
```

Весь оператор `ON DUPLICATE KEY UPDATE` копируется в тело процедуры
дословно, без какого-либо преобразования в `ON CONFLICT`.

## Наблюдаемая проблема

`CREATE PROCEDURE` проходит без ошибок — ora2pg выставляет в своём
выводе `check_function_bodies = false`, поэтому тело не разбирается на
загрузке. Падение происходит при первом же реальном вызове, подтверждено
на реальном PostgreSQL 16:

```
=# CALL bump(1);
ERROR:  syntax error at or near "DUPLICATE"
LINE 2:     ON DUPLICATE KEY UPDATE hits = hits + 1
               ^
QUERY:  INSERT INTO counters(id, hits) VALUES (p_id, 1)
    ON DUPLICATE KEY UPDATE hits = hits + 1
CONTEXT:  PL/pgSQL function bump(integer) line 3 at SQL statement
```

Загрузка самой схемы (`CREATE TABLE`, `CREATE PROCEDURE`) при этом
проходит чисто — на этом этапе ошибку заметить нельзя, только на
реальном вызове.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** У `INSERT`
в PostgreSQL нет такого синтаксиса вообще — переписывается на `INSERT
... ON CONFLICT (<уникальный_ключ>) DO UPDATE SET ...`. Реализовано:
`ora2pg_gap_report/detectors/mysql_on_duplicate_key_update.py`.
