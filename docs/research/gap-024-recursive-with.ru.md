# GAP-024: нативная рекурсивная `WITH ... AS (...)` без ключевого слова `RECURSIVE`

Oracle feature: рекурсивная факторизация подзапроса (recursive subquery
factoring) — `WITH cte (cols) AS (anchor UNION [ALL] recursive-branch)`,
где рекурсивная ветка ссылается на сам `cte`. Не то же самое, что
`CONNECT BY` (см. GAP-005) — это отдельный, современный, портируемый
способ писать рекурсивные запросы, без иерархических Oracle-расширений.
Oracle не требует явного ключевого слова `RECURSIVE` — рекурсия
определяется автоматически по самоссылке.

## Минимальный пример

```sql
WITH tree (employee_id, manager_id) AS (
    SELECT employee_id, manager_id FROM employees WHERE manager_id IS NULL
    UNION ALL
    SELECT e.employee_id, e.manager_id
    FROM employees e, tree t
    WHERE e.manager_id = t.employee_id
)
SELECT COUNT(*) INTO v_count FROM tree;
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

```sql
WITH tree(employee_id, manager_id) AS (
    ...
)
SELECT COUNT(*)                     FROM tree
```

`WITH` копируется как есть — ключевое слово `RECURSIVE` не добавлено.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` проходит без
ошибки, падает при первом вызове:

```
ERROR:  relation "tree" does not exist
DETAIL:  There is a WITH item named "tree", but it cannot be referenced
         from this part of the query.
HINT:  Use WITH RECURSIVE, or re-order the WITH items to remove forward
       references.
```

PostgreSQL требует ключевое слово `RECURSIVE` явно — без него самоссылка
на CTE во второй ветке `UNION` не резолвится.

Отдельно проверено: если Oracle-запрос дополнительно использует секцию
`CYCLE` (`WITH cte (...) CYCLE col SET flag TO 'Y' DEFAULT 'N' AS (...)`
— секция стоит перед `AS`), простого добавления `RECURSIVE` недостаточно
— в PostgreSQL секция `CYCLE` синтаксически идёт **после** закрывающей
скобки тела CTE, а не перед `AS`, и требует обязательную секцию `USING
path_column`, которой в Oracle-варианте нет вообще. То есть у запросов с
`CYCLE` это два накладывающихся друг на друга разных нарушения
совместимости, не одно.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/recursive_with.py`. Детектор ищет `WITH
name AS (` без предшествующего `RECURSIVE`, где тело содержит `UNION`
и имя CTE снова встречается в `FROM`-части одной из веток после первого
`UNION` — так исключаются как обычные, нерекурсивные `UNION`-CTE, так и
случайное совпадение имени CTE с алиасом столбца.
