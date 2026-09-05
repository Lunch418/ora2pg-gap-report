# GAP-076: `REPLACE INTO`

MySQL/MariaDB feature: вставить строку, а если строка с таким же
уникальным ключом уже есть — удалить её и вставить новую.

## Минимальный пример

```sql
CREATE TABLE cache1 (k VARCHAR(50) PRIMARY KEY, v INT);
CREATE PROCEDURE put_cache(IN p_k VARCHAR(50), IN p_v INT)
BEGIN
  REPLACE INTO cache1 (k, v) VALUES (p_k, p_v);
END;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE put_cache (IN p_k varchar(50), p_v integer) AS $body$
BEGIN
  REPLACE INTO cache1(k, v) VALUES (p_k, p_v);
END;
$body$
LANGUAGE PLPGSQL
;
```

Скопировано дословно, без какого-либо преобразования.

## Наблюдаемая проблема

Загрузка проходит чисто (`check_function_bodies = false` в выводе
ora2pg). При разборе тела на реальном PostgreSQL 16:

```
ERROR:  "cache1" is not a known variable
```

PostgreSQL разбирает `REPLACE` как начало присваивания переменной, а не
как оператор — своего `REPLACE INTO` у него нет.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.**
Переписывается на `INSERT ... ON CONFLICT (<ключ>) DO UPDATE SET ...`,
но перевод не дословный: `REPLACE` именно удаляет старую строку и
вставляет новую, поэтому по ней срабатывают `ON DELETE`-триггеры и
каскадные удаления дочерних строк, а не перечисленные в запросе столбцы
получают значения по умолчанию, а не сохраняют прежние. `ON CONFLICT DO
UPDATE` ведёт себя ровно наоборот. Реализовано:
`ora2pg_gap_report/detectors/mysql_replace_into.py`.
