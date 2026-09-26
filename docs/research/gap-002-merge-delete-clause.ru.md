# GAP-002: `MERGE ... DELETE WHERE` (составное предложение MERGE-DELETE в Oracle)

Oracle feature: необязательное предложение `DELETE WHERE` оператора
`MERGE`, вложенное в `WHEN MATCHED THEN UPDATE SET ...`, — удаляет только
что сопоставленные и обновлённые строки, если они ещё и удовлетворяют
условию удаления. Документированный стандартный синтаксис Oracle (SQL
Language Reference, оператор `MERGE`).

## Минимальный пример

```sql
MERGE INTO customers c
USING staging_customers s
ON (c.customer_id = s.customer_id)
WHEN MATCHED THEN
  UPDATE SET c.name = s.name, c.updated_at = SYSDATE
  WHERE s.name IS NOT NULL
  DELETE WHERE s.is_deleted = 1
WHEN NOT MATCHED THEN
  INSERT (customer_id, name, created_at)
  VALUES (s.customer_id, s.name, SYSDATE);
```

## Вывод ora2pg (v25.0, `-t PACKAGE`, по умолчанию и с `PG_VERSION 16` — одинаково)

Оператор `MERGE` переносится почти дословно (только `SYSDATE` →
`clock_timestamp()` и поправка на эквивалентность пустой строки и NULL в
Oracle в `WHERE`). Предложение `DELETE WHERE s.is_deleted = 1` остаётся
ровно в том виде, как написано.

## Наблюдаемая проблема

У `MERGE` в PostgreSQL (15+) нет аналога составного предложения Oracle
`UPDATE SET ... WHERE ... DELETE WHERE ...`: каждая ветка `WHEN` — одно
действие (`UPDATE`, `DELETE`, `INSERT` или `DO NOTHING`), и у поведения
Oracle «удалить часть сопоставленных и обновлённых строк» нет прямого
синтаксиса. Эквивалент в PostgreSQL требует разбить её на две ветки
`WHEN MATCHED` с взаимодополняющими условиями.

Подтверждено на настоящем сервере PostgreSQL 16: `CREATE PROCEDURE`
проходит молча (вывод ora2pg ставит `SET check_function_bodies = false`,
поэтому тело при создании не разбирается), а ошибка появляется только при
первом настоящем `CALL`:

```
ERROR:  syntax error at or near "WHERE"
LINE 6:       WHERE (s.name IS NOT NULL AND s.name::text <> '')
              ^
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0. Версия PostgreSQL: 16.

## Проверка границ: обычный `MERGE` (без `DELETE WHERE`)

Проверено отдельно: `MERGE` только с `WHEN MATCHED THEN UPDATE SET ...` и
`WHEN NOT MATCHED THEN INSERT ...` (без `DELETE WHERE`) конвертируется
правильно и загружается и выполняется в PostgreSQL 16 без ошибок.
**Обычный `MERGE` — не gap**: его обнаружение было бы ровно тем ложным
срабатыванием по ключевому слову, которого методология проекта избегает.

## Вердикт

**Gap подтверждён, узко ограничен подпредложением `DELETE WHERE` в
`MERGE`.** Опасен именно тем, что при создании объекта падает молча, а
ошибку даёт только при выполнении: миграция может пройти проверку «всё ли
компилируется» и всё равно сломаться в проде в первый же раз, когда
выполнится эта ветка кода.

Реализован детектор: `ora2pg_gap_report/detectors/merge_delete_clause.py`
— отмечает `DELETE\s+WHERE` внутри ветки `WHEN MATCHED` оператора `MERGE`
в исходном коде Oracle (дешёвая проверка по исходнику, без запуска
`ora2pg`, как и у `autonomous_tx`/`compound_triggers`/`dbms_utl_calls`).
