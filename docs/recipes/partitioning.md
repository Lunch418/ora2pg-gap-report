*English | [Русский](partitioning.ru.md)*

# Partitioned tables

Covers: GAP-013 (`table_partitioning`).

## The problem

`ora2pg` drops the `PARTITION BY` clause and every partition (checked for
`RANGE`, `LIST`, `HASH`, `REFERENCE` and `SYSTEM` with `-t TABLE`): the table
arrives as one ordinary table, with no error, no warning and nothing in
`--estimate_cost` (GAP-013). Everything still works, until the data volume the
partitioning was there for arrives, or a job that drops old partitions
finds none.

PostgreSQL has declarative partitioning with the same three kinds, `RANGE`,
`LIST` and `HASH`, so most definitions carry over almost word for word.
The differences are in what Oracle does automatically.

## RANGE, with a default partition

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
    PRIMARY KEY (order_id, order_date)    -- must include the partition key
) PARTITION BY RANGE (order_date);

-- VALUES LESS THAN (x) -> FROM (previous bound) TO (x); FROM is inclusive, TO is not
CREATE TABLE orders_p2026_01 PARTITION OF orders
    FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE orders_p2026_02 PARTITION OF orders
    FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
-- VALUES LESS THAN (MAXVALUE), and anything else no partition takes
CREATE TABLE orders_p_max PARTITION OF orders DEFAULT;

INSERT INTO orders VALUES (1, '2026-01-15', 10), (2, '2026-02-20', 20), (3, '2027-07-01', 30);

DO $$
BEGIN
    ASSERT (SELECT tableoid::regclass::text FROM orders WHERE order_id = 1) = 'orders_p2026_01';
    ASSERT (SELECT tableoid::regclass::text FROM orders WHERE order_id = 3) = 'orders_p_max';
END $$;
```

Oracle's first partition has no lower bound. Give the PostgreSQL one an
explicit `FROM (MINVALUE)` if rows older than your first real bound can
exist, or let them land in the default partition.

## LIST and HASH

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

Composite partitioning (`SUBPARTITION BY`) is a partition that is itself
partitioned: `CREATE TABLE ... PARTITION OF parent FOR VALUES ...
PARTITION BY HASH (...)`, then its own partitions.

## What Oracle did for you

| Oracle | PostgreSQL |
|---|---|
| `INTERVAL (NUMTOYMINTOINTERVAL(1, 'MONTH'))`: new partitions appear on insert | nothing appears by itself: create partitions ahead with a scheduled job, or use the `pg_partman` extension; meanwhile the default partition catches what has no home |
| a global index, unique on any column | indexes are per partition; a `UNIQUE`/`PRIMARY KEY` must include every partition key column |
| `ALTER TABLE ... DROP PARTITION p` | `DROP TABLE orders_p2026_01` (or `DETACH PARTITION` first to keep the data) |
| `ALTER TABLE ... TRUNCATE PARTITION p` | `TRUNCATE orders_p2026_01` |
| `EXCHANGE PARTITION` | `DETACH PARTITION` + `ATTACH PARTITION` |
| `SPLIT PARTITION` / `MERGE PARTITIONS` | detach, move the rows, attach the new partitions |
| reference partitioning (`PARTITION BY REFERENCE`) | none: partition the child by the same key, copied into it |

The unique-key rule is the one that changes table design. If Oracle had
`order_id` unique across all partitions through a global index, PostgreSQL
cannot enforce exactly that on a table partitioned by `order_date`. Either
make the key `(order_id, order_date)`, as above, or keep the uniqueness in
the sequence that generates `order_id` and accept it is not enforced.

```sql
DO $$
BEGIN
    BEGIN
        EXECUTE 'ALTER TABLE orders ADD CONSTRAINT orders_id_uq UNIQUE (order_id)';
        RAISE EXCEPTION 'a unique key without the partition key was accepted';
    EXCEPTION WHEN feature_not_supported THEN
        NULL;  -- expected: it must include order_date
    END;
END $$;
```

## Watch out for

- **Partition pruning needs the key in the query.** A query without
  `order_date` in its `WHERE` reads every partition. Check the plans of the
  queries the partitioning was built for.
- **The data load.** `ora2pg` loads data with `COPY` into the table it
  created. Create the partitioned table yourself before loading, so rows
  are routed into partitions on the way in.
