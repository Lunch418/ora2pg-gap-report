*[English](hierarchical-queries.md) | Русский*

# Иерархические запросы: CONNECT BY -> WITH RECURSIVE

Покрывает: GAP-005 (`connect_by`), GAP-014 (`connect_by_nocycle`), GAP-024
(`recursive_with`), GAP-039 (`connect_by_pseudocolumn`).

## Проблема

Обычный `CONNECT BY` `ora2pg` превращает в `WITH RECURSIVE`, но неверно
считает `LEVEL` (GAP-005), разваливает окружающий блок, если есть `NOCYCLE`
или `ORDER SIBLINGS BY` (GAP-014), оставляет как есть `CONNECT_BY_ROOT`,
`CONNECT_BY_ISLEAF` и `CONNECT_BY_ISCYCLE` (GAP-039) и копирует
рекурсивный `WITH`, который Oracle выполняет без ключевого слова
`RECURSIVE` (GAP-024). В PostgreSQL всё это решается одним приёмом:
рекурсия пишется явно, а то, что Oracle вычисляет сам, переносится в
столбцы.

Запрос Oracle, который переписывается на этой странице:

```plsql
SELECT employee_id,
       LEVEL                               AS lvl,
       SYS_CONNECT_BY_PATH(last_name, '/') AS path,
       CONNECT_BY_ROOT last_name           AS root_name,
       CONNECT_BY_ISLEAF                   AS is_leaf
FROM employees
START WITH manager_id IS NULL
CONNECT BY PRIOR employee_id = manager_id
ORDER SIBLINGS BY last_name;
```

## Как это пишется в PostgreSQL

```sql
CREATE TABLE employees (
    employee_id integer PRIMARY KEY,
    manager_id  integer REFERENCES employees,
    last_name   text NOT NULL
);
INSERT INTO employees VALUES
    (1, NULL, 'King'),
    (2, 1, 'Kochhar'),
    (3, 1, 'De Haan'),
    (4, 2, 'Greenberg'),
    (5, 3, 'Hunold'),
    (6, 4, 'Faviet');

CREATE VIEW employee_tree AS
WITH RECURSIVE tree AS (
    -- START WITH
    SELECT employee_id,
           manager_id,
           last_name,
           1                    AS lvl,        -- LEVEL
           '/' || last_name     AS path,       -- SYS_CONNECT_BY_PATH
           last_name            AS root_name,  -- CONNECT_BY_ROOT
           ARRAY[last_name]     AS sibling_key -- ORDER SIBLINGS BY
    FROM employees
    WHERE manager_id IS NULL
    UNION ALL
    -- CONNECT BY PRIOR employee_id = manager_id
    SELECT e.employee_id,
           e.manager_id,
           e.last_name,
           t.lvl + 1,
           t.path || '/' || e.last_name,
           t.root_name,
           t.sibling_key || e.last_name
    FROM employees e
    JOIN tree t ON e.manager_id = t.employee_id
)
SELECT employee_id,
       lvl,
       path,
       root_name,
       -- CONNECT_BY_ISLEAF
       NOT EXISTS (SELECT 1 FROM employees c WHERE c.manager_id = tree.employee_id) AS is_leaf,
       sibling_key
FROM tree;

SELECT employee_id, lvl, path, root_name, is_leaf
FROM employee_tree
ORDER BY sibling_key;  -- это и есть ORDER SIBLINGS BY
```

Что чем заменяется:

| Oracle | PostgreSQL |
|---|---|
| `START WITH условие` | первая ветка `UNION ALL` |
| `CONNECT BY PRIOR a = b` | соединение во второй ветке, `child.b = tree.a` |
| `LEVEL` | столбец-счётчик: `1`, дальше `родитель + 1` |
| `SYS_CONNECT_BY_PATH(x, '/')` | текстовый столбец, который строится так же |
| `CONNECT_BY_ROOT x` | столбец, заданный в первой ветке и копируемый вниз |
| `CONNECT_BY_ISLEAF` | `NOT EXISTS` дочерней строки |
| `ORDER SIBLINGS BY x` | массив значений `x` вдоль пути, затем `ORDER BY` по нему |

Проверки ниже выполняются вместе с рецептом в тестах:

```sql
DO $$
BEGIN
    ASSERT (SELECT lvl FROM employee_tree WHERE employee_id = 6) = 4;
    ASSERT (SELECT path FROM employee_tree WHERE employee_id = 6) = '/King/Kochhar/Greenberg/Faviet';
    ASSERT (SELECT bool_and(root_name = 'King') FROM employee_tree);
    ASSERT (SELECT array_agg(employee_id ORDER BY employee_id) FROM employee_tree WHERE is_leaf) = ARRAY[5, 6];
    -- соседи по имени: ветка De Haan раньше ветки Kochhar
    ASSERT (SELECT array_agg(employee_id ORDER BY sibling_key) FROM employee_tree) = ARRAY[1, 3, 5, 2, 4, 6];
END $$;
```

`sibling_key` сортирует только по имени, как `ORDER SIBLINGS BY last_name`
в Oracle. Если у двух соседей может совпасть имя и порядок между ними
важен, добавьте в массив и ключ, например
`ARRAY[last_name || ':' || employee_id]`, или используйте массив
составного типа.

## NOCYCLE и CONNECT_BY_ISCYCLE

Таблица, где у каждой строки один родитель, не может зациклиться обратно
к корню, поэтому циклы бывают в таблицах связей. В Oracle `CONNECT BY
NOCYCLE` останавливается перед строкой, которая повторилась бы, а
`CONNECT_BY_ISCYCLE` равен `1` на строке, чей потомок замкнул бы цикл.
Для первой половины в PostgreSQL 14 и новее есть предложение `CYCLE`:

```sql
CREATE TABLE links (from_id integer, to_id integer);
INSERT INTO links VALUES (1, 2), (2, 3), (3, 1), (3, 4);

CREATE VIEW link_walk AS
WITH RECURSIVE walk AS (
    SELECT to_id AS node, 1 AS lvl
    FROM links
    WHERE from_id = 1
    UNION ALL
    SELECT l.to_id, w.lvl + 1
    FROM links l
    JOIN walk w ON l.from_id = w.node
) CYCLE node SET is_cycle USING visited
SELECT node,
       lvl,
       -- CONNECT_BY_ISCYCLE: потомок этой строки уже есть на её пути
       EXISTS (
           SELECT 1 FROM links l
           WHERE l.from_id = walk.node
             AND ROW(l.to_id) = ANY (walk.visited)
       ) AS is_cycle_row
FROM walk
WHERE NOT is_cycle;  -- NOCYCLE: убрать повторившуюся строку

DO $$
BEGIN
    ASSERT (SELECT array_agg(node ORDER BY lvl, node) FROM link_walk) = ARRAY[2, 3, 1, 4];
    ASSERT (SELECT array_agg(node ORDER BY node) FROM link_walk WHERE is_cycle_row) = ARRAY[1];
END $$;
```

`CYCLE node SET is_cycle USING visited` добавляет два столбца: `is_cycle`
истинен на строке, которая повторила бы узел, а `visited` хранит путь как
массив строк. Фильтр `NOT is_cycle` даёт ровно те строки, что вернул бы
`NOCYCLE` в Oracle.

Начальные строки здесь - связи *из* узла 1, поэтому сам узел 1 появляется,
когда обход к нему возвращается. Oracle ведёт себя так же, если строки
`START WITH` - это связи.

## Рекурсивный WITH без RECURSIVE

Oracle 11gR2 и новее принимает рекурсивный подзапрос без всякого
ключевого слова. PostgreSQL требует `WITH RECURSIVE`, и в этом всё
исправление. Собственные предложения Oracle `SEARCH DEPTH FIRST BY ... SET`
и `CYCLE ... SET ... TO ... DEFAULT` соответствуют `SEARCH DEPTH FIRST BY
... SET` и `CYCLE ... SET ... USING` из PostgreSQL 14:

```sql
WITH RECURSIVE numbers (n) AS (
    SELECT 1
    UNION ALL
    SELECT n + 1 FROM numbers WHERE n < 5
) SEARCH DEPTH FIRST BY n SET ordering
SELECT n FROM numbers ORDER BY ordering;
```

## На что обратить внимание

- **Производительность.** Oracle оптимизирует `CONNECT BY` внутри себя.
  Рекурсивный CTE делает соединение на каждом уровне: нужен индекс по
  столбцу соединения (здесь `manager_id`).
- **Фильтры.** `WHERE` в иерархическом запросе Oracle применяется *после*
  построения иерархии, а условие внутри `CONNECT BY` отсекает целые ветки.
  Первое идёт во внешний `SELECT`, второе - в условие `JOIN` рекурсивной
  ветки.
- **`LEVEL` в выводе `ora2pg`.** Если вы оставляете сгенерированный запрос
  вместо переписывания, проверьте каждый `LEVEL`: GAP-005 - это ровно этот
  столбец, посчитанный неверно. Их находит
  `ora2pg-gap-report --check-connect-by`.
