# GAP-077: `INSERT IGNORE`

MySQL/MariaDB feature: вставка, превращающая ошибки в предупреждения и
молча пропускающая проблемные строки.

## Минимальный пример

```sql
CREATE TABLE uniq1 (id INT PRIMARY KEY, v INT);
CREATE PROCEDURE add_uniq(IN p_id INT)
BEGIN
  INSERT IGNORE INTO uniq1 (id, v) VALUES (p_id, 1);
END;
```

## Вывод ora2pg (v25.0, `-m -t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE add_uniq (IN p_id integer) AS $body$
BEGIN
  INSERT IGNORE INTO uniq1(id, v) VALUES (p_id, 1);
END;
$body$
LANGUAGE PLPGSQL
;
```

Скопировано дословно.

## Наблюдаемая проблема

Загрузка проходит чисто (`check_function_bodies = false` в выводе
ora2pg). При разборе тела на реальном PostgreSQL 16:

```
ERROR:  "uniq1" is not a known variable
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16. Source
dialect: MySQL (`ora2pg -m`).

## Вердикт

**Gap подтверждён, severity high, failure_stage runtime.** Ближайший
аналог — `INSERT ... ON CONFLICT DO NOTHING`, но он уже по охвату:
`IGNORE` в MySQL глушит не только конфликт уникальности, но и другие
ошибки вставки, вплоть до обрезания слишком длинных значений и
подстановки нулей вместо некорректных дат. Если код полагался именно на
это широкое поведение, дословный перевод изменит смысл. Реализовано:
`ora2pg_gap_report/detectors/mysql_insert_ignore.py`.
