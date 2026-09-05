# GAP-016: `INSERT ALL` / `INSERT FIRST` — многотабличная вставка

Oracle feature: `INSERT ALL`/`INSERT FIRST` — многотабличная вставка,
условная (`WHEN ... THEN INTO ...`) или безусловная (несколько `INTO`
подряд без `WHEN`), одним запросом распределяющая строки источника по
нескольким целевым таблицам.

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE split_orders AS
BEGIN
    INSERT ALL
        WHEN amount > 1000 THEN
            INTO big_orders (order_id, amount)
            VALUES (order_id, amount)
        WHEN amount <= 1000 THEN
            INTO small_orders (order_id, amount)
            VALUES (order_id, amount)
    SELECT order_id, amount FROM staging_orders;
END;
/
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Конструкция копируется как есть, без единого изменения — ни `INSERT ALL`,
ни секции `INTO`/`WHEN` не переписаны.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` проходит без
ошибки (`check_function_bodies = false`), но падает уже на этапе
компиляции тела при первом `CALL`:

```
ERROR:  "big_orders" is not a known variable
LINE 5:                 INTO big_orders(order_id, amount)
                             ^
```

PL/pgSQL интерпретирует `INTO таблица` как форму `SELECT ... INTO
переменная` (используемую для присваивания результата запроса
PL/pgSQL-переменной), а не как ветку многотабличной вставки — у
PostgreSQL нет синтаксиса многотабличного `INSERT` вообще.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/insert_all.py`. Флагует и `INSERT ALL`, и
`INSERT FIRST`, включая безусловный вариант без `WHEN` — единственное
требование — наличие `INTO` в разумном окне после ключевого слова
(что верно для любого реального многотабличного `INSERT`).
