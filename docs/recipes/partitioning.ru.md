*[English](partitioning.md) | Русский*

# Секционированные таблицы

Покрывает: GAP-013 (`table_partitioning`).

## Проблема

`ora2pg` выбрасывает предложение `PARTITION BY` и все секции (проверено для
`RANGE`, `LIST`, `HASH`, `REFERENCE` и `SYSTEM` с `-t TABLE`): таблица
приходит одной обычной таблицей, без ошибки, без предупреждения и без
следа в `--estimate_cost` (GAP-013). Всё продолжает работать, пока не
придёт тот объём данных, ради которого секционирование и делали, или пока
задание, удаляющее старые секции, не обнаружит, что удалять нечего.

В PostgreSQL есть декларативное секционирование тех же трёх видов,
`RANGE`, `LIST` и `HASH`, так что большинство определений переносится
почти слово в слово. Различия - в том, что Oracle делает сам.

## RANGE и секция по умолчанию

```plsql
CREATE TABLE orders (
    order_id   NUMBER,
    order_date DATE NOT NULL,
    amount     NUMBER
)
PARTITION BY RANGE (order_date) (
    PARTITION p2026_01 VALUES LESS THAN (DATE '2026-02-01'),
    PARTITION p2026_02 VALUES LESS THAN (DATE '2026-03-01'),
    PARTITION p_max    VALUES LESS THAN (MAXVALUE)
);
```

```sql
CREATE TABLE orders (
    order_id   bigint  NOT NULL,
    order_date date    NOT NULL,
    amount     numeric,
    PRIMARY KEY (order_id, order_date)    -- обязан включать ключ секционирования
) PARTITION BY RANGE (order_date);

-- VALUES LESS THAN (x) -> FROM (предыдущая граница) TO (x); FROM включительно, TO нет
CREATE TABLE orders_p2026_01 PARTITION OF orders
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE orders_p2026_02 PARTITION OF orders
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
-- VALUES LESS THAN (MAXVALUE) и всё, что не взяла ни одна секция
CREATE TABLE orders_p_max PARTITION OF orders DEFAULT;

INSERT INTO orders VALUES (1, '2026-01-15', 10), (2, '2026-02-20', 20), (3, '2027-07-01', 30);

DO $$
BEGIN
    ASSERT (SELECT tableoid::regclass::text FROM orders WHERE order_id = 1) = 'orders_p2026_01';
    ASSERT (SELECT tableoid::regclass::text FROM orders WHERE order_id = 3) = 'orders_p_max';
END $$;
```

У первой секции Oracle нет нижней границы. Дайте первой секции PostgreSQL
явное `FROM (MINVALUE)`, если могут быть строки старше первой настоящей
границы, или пусть они попадают в секцию по умолчанию.

## LIST и HASH

```sql
CREATE TABLE customers (
    customer_id integer NOT NULL,
    region      text    NOT NULL
) PARTITION BY LIST (region);
CREATE TABLE customers_eu PARTITION OF customers FOR VALUES IN ('DE', 'FR', 'NL');
CREATE TABLE customers_us PARTITION OF customers FOR VALUES IN ('US');
CREATE TABLE customers_other PARTITION OF customers DEFAULT;   -- VALUES (DEFAULT)

-- PARTITION BY HASH (id) PARTITIONS 4
CREATE TABLE events (id bigint NOT NULL, payload text) PARTITION BY HASH (id);
CREATE TABLE events_0 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 0);
CREATE TABLE events_1 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 1);
CREATE TABLE events_2 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 2);
CREATE TABLE events_3 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 3);

INSERT INTO customers VALUES (1, 'FR'), (2, 'BR');
INSERT INTO events SELECT g, 'x' FROM generate_series(1, 100) AS g;

DO $$
BEGIN
    ASSERT (SELECT tableoid::regclass::text FROM customers WHERE customer_id = 2) = 'customers_other';
    ASSERT (SELECT count(DISTINCT tableoid) FROM events) = 4;
END $$;
```

Составное секционирование (`SUBPARTITION BY`) - это секция, которая сама
секционирована: `CREATE TABLE ... PARTITION OF parent FOR VALUES ...
PARTITION BY HASH (...)`, а затем её собственные секции.

## Что Oracle делал за вас

| Oracle | PostgreSQL |
|---|---|
| `INTERVAL (NUMTOYMINTOINTERVAL(1, 'MONTH'))`: новые секции появляются при вставке | само ничего не появляется: создавайте секции заранее заданием по расписанию или через расширение `pg_partman`; пока их нет, бездомные строки ловит секция по умолчанию |
| глобальный индекс, уникальный по любому столбцу | индексы у каждой секции свои; `UNIQUE`/`PRIMARY KEY` обязан включать все столбцы ключа секционирования |
| `ALTER TABLE ... DROP PARTITION p` | `DROP TABLE orders_p2026_01` (или сначала `DETACH PARTITION`, чтобы сохранить данные) |
| `ALTER TABLE ... TRUNCATE PARTITION p` | `TRUNCATE orders_p2026_01` |
| `EXCHANGE PARTITION` | `DETACH PARTITION` + `ATTACH PARTITION` |
| `SPLIT PARTITION` / `MERGE PARTITIONS` | отсоединить, перенести строки, присоединить новые секции |
| ссылочное секционирование (`PARTITION BY REFERENCE`) | нет: секционируйте дочернюю таблицу по тому же ключу, скопированному в неё |

Правило про уникальные ключи меняет устройство таблицы. Если в Oracle
`order_id` был уникален во всех секциях благодаря глобальному индексу, на
таблице, секционированной по `order_date`, PostgreSQL ровно это обеспечить
не может. Либо сделайте ключ `(order_id, order_date)`, как выше, либо
оставьте уникальность последовательности, которая выдаёт `order_id`, и
примите, что база её не проверяет.

```sql
DO $$
BEGIN
    BEGIN
        EXECUTE 'ALTER TABLE orders ADD CONSTRAINT orders_id_uq UNIQUE (order_id)';
        RAISE EXCEPTION 'уникальный ключ без ключа секционирования принят';
    EXCEPTION WHEN feature_not_supported THEN
        NULL;  -- так и должно быть: ключ обязан включать order_date
    END;
END $$;
```

## На что обратить внимание

- **Отсечение секций требует ключа в запросе.** Запрос без `order_date` в
  `WHERE` читает все секции. Проверьте планы тех запросов, ради которых
  секционирование и строили.
- **Загрузка данных.** `ora2pg` загружает данные через `COPY` в ту таблицу,
  которую создал. Создайте секционированную таблицу сами до загрузки, тогда
  строки по пути разойдутся по секциям.
