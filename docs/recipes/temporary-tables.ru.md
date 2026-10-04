*[English](temporary-tables.md) | Русский*

# Глобальные временные таблицы

Покрывает: GAP-012 (`global_temp_table`), GAP-111 (`mysql_temporary_table`).

## Проблема

Словом "временная" называют две разные вещи.

**Глобальная временная таблица** Oracle - постоянный объект схемы: она
создаётся один раз, видна всем сессиям, каждая сессия видит только свои
строки, и по умолчанию они очищаются при `COMMIT` (`ON COMMIT DELETE
ROWS`). `ora2pg` превращает её в `CREATE TEMPORARY TABLE` и теряет
предложение `ON COMMIT` (GAP-012). Это ломает её дважды:

- умолчание PostgreSQL противоположное, `ON COMMIT PRESERVE ROWS`, поэтому
  строки переживают коммит, на котором Oracle их бы очистил;
- временная таблица PostgreSQL существует только в той сессии, которая её
  создала. Выполните сгенерированный DDL один раз при развёртывании, и
  таблица будет только у сессии развёртывания; каждая сессия приложения,
  которая к ней обратится, получит `relation "..." does not exist`.

`CREATE TEMPORARY TABLE` в MySQL, наоборот, и так создаётся во время работы
той сессией, которая её использует. `ora2pg` убирает `TEMPORARY` и делает
её постоянной таблицей, общей для всех (GAP-111): верните ключевое слово.

## Приём: создавать таблицу в той сессии, которая её использует

Замените DDL функцией, которая создаёт таблицу, если в этой сессии её ещё
нет, и вызывайте её перед первым использованием:

```sql
CREATE FUNCTION staging_orders_ensure()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    CREATE TEMPORARY TABLE IF NOT EXISTS staging_orders (
        order_id integer PRIMARY KEY,
        amount   numeric NOT NULL
    ) ON COMMIT DELETE ROWS;   -- умолчание Oracle; PRESERVE ROWS, если так было в GTT
END;
$$;

CREATE FUNCTION staging_orders_total()
RETURNS numeric
LANGUAGE plpgsql
AS $$
BEGIN
    PERFORM staging_orders_ensure();
    INSERT INTO staging_orders VALUES (1, 10), (2, 32);
    RETURN (SELECT sum(amount) FROM staging_orders);
END;
$$;

DO $$
BEGIN
    ASSERT staging_orders_total() = 42;
    -- повторный вызов в той же сессии не должен падать на существующей таблице
    PERFORM staging_orders_ensure();
    ASSERT (SELECT relpersistence FROM pg_class WHERE oid = 'staging_orders'::regclass) = 't';
END $$;
```

Про этот приём:

- `IF NOT EXISTS` делает все вызовы после первого дешёвыми (уведомление, не
  ошибка). Если уведомление мешает, поднимите `client_min_messages` до
  `warning`.
- Индексы тоже создаются в функции, сразу после таблицы; они такие же
  временные, как таблица.
- Временная таблица не видна другим сессиям - ровно как в Oracle; выдавать
  `GRANT` не нужно.
- Никогда не кладите `CREATE TEMPORARY TABLE` для GTT из Oracle в скрипт
  развёртывания. Он выполнится успешно и спрячет проблему до первой
  настоящей сессии.

## ON COMMIT рядом

| Oracle | PostgreSQL |
|---|---|
| `ON COMMIT DELETE ROWS` или `ON COMMIT` нет совсем | `ON COMMIT DELETE ROWS` (писать обязательно) |
| `ON COMMIT PRESERVE ROWS` | `ON COMMIT PRESERVE ROWS` или ничего (это умолчание) |
| (сессия завершилась) | таблица и её строки исчезают |

В PostgreSQL есть ещё `ON COMMIT DROP`: при коммите удаляется сама
таблица. Аналога в Oracle у этого нет.

## Если таблица используется очень часто

Создание временной таблицы трогает системный каталог. Код, который создаёт
и удаляет их тысячи раз в минуту, раздувает `pg_class` и `pg_attribute`.
Два выхода:

- расширение `pgtt`, которое эмулирует глобальные временные таблицы в духе
  Oracle (одно определение, строки у каждой сессии свои) поверх PostgreSQL;
- обычная **нежурналируемая** таблица со столбцом-ключом сессии, которую
  заполняют и очищают явно:

```sql
CREATE UNLOGGED TABLE staging_orders_shared (
    session_pid integer NOT NULL DEFAULT pg_backend_pid(),
    order_id    integer NOT NULL,
    amount      numeric NOT NULL,
    PRIMARY KEY (session_pid, order_id)
);

CREATE VIEW staging_orders_mine AS
    SELECT order_id, amount FROM staging_orders_shared WHERE session_pid = pg_backend_pid();

INSERT INTO staging_orders_shared (order_id, amount) VALUES (1, 5);
DO $$
BEGIN
    ASSERT (SELECT sum(amount) FROM staging_orders_mine) = 5;
END $$;
-- то, что за вас делал ON COMMIT DELETE ROWS, вручную:
DELETE FROM staging_orders_shared WHERE session_pid = pg_backend_pid();
```

С общей таблицей строки сессии, которая упала, остаются; периодически
удаляйте строки, чьего `session_pid` больше нет в `pg_stat_activity`.

## Временные таблицы MySQL

Код MySQL и так создаёт свои временные таблицы во время работы. Оставьте
команду на месте и оставьте ключевое слово:

```sql
CREATE TEMPORARY TABLE IF NOT EXISTS report_rows (
    id    integer,
    label text
);  -- MySQL: строки живут всю сессию, в PostgreSQL это тоже умолчание
```
