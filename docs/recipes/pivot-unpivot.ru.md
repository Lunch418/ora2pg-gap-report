*[English](pivot-unpivot.md) | Русский*

# PIVOT и UNPIVOT

Покрывает: GAP-008 (`pivot_clause`).

## Проблема

`PIVOT` превращает значения строк в столбцы, `UNPIVOT` делает обратное. В
PostgreSQL нет ни того, ни другого ключевого слова, а `ora2pg` копирует
оба как есть, и команда падает. У обоих есть эквиваленты на обычном SQL,
такие же короткие и без расширений.

Данные для этой страницы:

```sql
CREATE TABLE sales (
    region  text    NOT NULL,
    quarter text    NOT NULL,
    amount  numeric NOT NULL
);
INSERT INTO sales VALUES
    ('north', 'Q1', 100), ('north', 'Q2', 150), ('north', 'Q2', 50),
    ('south', 'Q1', 80),  ('south', 'Q3', 120);
```

## PIVOT -> агрегаты с FILTER

```plsql
SELECT *
FROM (SELECT region, quarter, amount FROM sales)
PIVOT (SUM(amount) FOR quarter IN ('Q1' AS q1, 'Q2' AS q2, 'Q3' AS q3));
```

```sql
CREATE VIEW sales_by_quarter AS
SELECT region,
       sum(amount) FILTER (WHERE quarter = 'Q1') AS q1,
       sum(amount) FILTER (WHERE quarter = 'Q2') AS q2,
       sum(amount) FILTER (WHERE quarter = 'Q3') AS q3
FROM sales
GROUP BY region;

DO $$
BEGIN
    ASSERT (SELECT q2 FROM sales_by_quarter WHERE region = 'north') = 200;
    ASSERT (SELECT q2 FROM sales_by_quarter WHERE region = 'south') IS NULL;
END $$;
```

Правила переписывания:

- каждый столбец источника, который не стоит в агрегате и не стоит в `FOR`,
  становится столбцом `GROUP BY` (здесь `region`);
- каждое значение из `IN (...)` становится одним агрегатом с
  `FILTER (WHERE столбец_for = значение)` и именем из своего псевдонима;
- несколько агрегатов в одном `PIVOT` (`SUM(amount) AS s, COUNT(*) AS c`)
  дают по столбцу на каждое значение и каждый агрегат:
  `sum(...) FILTER (...) AS q1_s`, `count(*) FILTER (...) AS q1_c`.

Как и в Oracle, значение без строк даёт `NULL`, а не `0`; оберните в
`coalesce(..., 0)`, где нужен ноль.

`PIVOT XML` и динамический `IN (ANY)` дают список столбцов, зависящий от
данных. SQL в PostgreSQL требует знать столбцы заранее: соберите команду
в PL/pgSQL через `format()` и `EXECUTE` или верните пары как `jsonb`
(`jsonb_object_agg(quarter, total)`) и разверните их на клиенте.

Другой известный ответ - `crosstab()` из расширения `tablefunc`. Он
работает, но список столбцов всё равно надо выписать в вызове, и с
пропущенными значениями в нём легко ошибиться; `FILTER` проще и не требует
расширения.

## UNPIVOT -> LATERAL VALUES

```plsql
SELECT region, quarter, amount
FROM sales_by_quarter
UNPIVOT (amount FOR quarter IN (q1 AS 'Q1', q2 AS 'Q2', q3 AS 'Q3'));
```

```sql
CREATE VIEW sales_unpivoted AS
SELECT s.region, v.quarter, v.amount
FROM sales_by_quarter s
CROSS JOIN LATERAL (
    VALUES ('Q1', s.q1), ('Q2', s.q2), ('Q3', s.q3)
) AS v(quarter, amount)
WHERE v.amount IS NOT NULL;   -- по умолчанию UNPIVOT работает как EXCLUDE NULLS

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM sales_unpivoted) = 4;
    ASSERT (SELECT amount FROM sales_unpivoted WHERE region = 'south' AND quarter = 'Q3') = 120;
END $$;
```

`UNPIVOT INCLUDE NULLS` - тот же запрос без `WHERE`. Разворот сразу
нескольких столбцов (`UNPIVOT ((a, b) FOR ...)`) - тот же список `VALUES`,
только столбцов в строке больше.

## На что обратить внимание

- **Типы.** `UNPIVOT` требует, чтобы разворачиваемые столбцы были одного
  типа, `VALUES` тоже. Где типы разные, приведите (`s.q1::text`).
- **Неявная группировка.** `PIVOT` группирует по *всем* оставшимся
  столбцам источника. Если `PIVOT` стоит прямо на широкой таблице, а не на
  подзапросе, в группировку молча попадают все её столбцы; в переписанном
  запросе перечисляйте столбцы `GROUP BY` осознанно.
