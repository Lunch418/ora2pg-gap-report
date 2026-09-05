# GAP-038: `MATCH_RECOGNIZE` — сопоставление строк с шаблоном

Oracle feature: `MATCH_RECOGNIZE` (12c+) — поиск последовательностей строк,
соответствующих шаблону-регулярке, прямо в SQL: разбиение на разделы,
упорядочивание, объявление переменных шаблона (`DEFINE`), вычисление
значений по найденному совпадению (`MEASURES`).

## Минимальный пример

```sql
CREATE OR REPLACE VIEW v_price_runs AS
SELECT *
FROM ticker_prices
MATCH_RECOGNIZE (
  PARTITION BY symbol
  ORDER BY price_date
  MEASURES STRT.price_date AS start_date,
           LAST(UP.price_date) AS end_date
  ONE ROW PER MATCH
  PATTERN (STRT UP+)
  DEFINE UP AS UP.price > PREV(UP.price)
);
```

## Вывод ora2pg (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_price_runs AS SELECT *
FROM ticker_prices
MATCH_RECOGNIZE(
  PARTITION BY symbol
  ORDER BY price_date
  MEASURES STRT.price_date AS start_date,
           LAST(UP.price_date) AS end_date
  ONE ROW PER MATCH
  PATTERN(STRT UP+)
  DEFINE UP AS UP.price > PREV(UP.price)
);
```

Конструкция скопирована в вывод как есть — ora2pg не пытается её
конвертировать и не предупреждает о ней.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 — падает при загрузке
сгенерированного DDL:

```
ERROR:  syntax error at or near "BY"
LINE 4:   PARTITION BY symbol
                    ^
```

У PostgreSQL нет row pattern matching ни в каком виде — ни на уровне
синтаксиса, ни расширением из коробки.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/match_recognize.py`. Ручная переработка:
оконные функции (`LAG`/`LEAD` над разделом) с последующей фильтрацией,
либо рекурсивный CTE — прямой замены одной конструкцией не существует.
