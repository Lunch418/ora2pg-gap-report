# GAP-042: `SAMPLE (n)` — выборка процента строк

Oracle feature: выборка случайного процента строк (`SAMPLE`) или блоков
(`SAMPLE BLOCK`) таблицы прямо во `FROM`.

## Минимальный пример

```sql
CREATE OR REPLACE VIEW v_sampled AS
SELECT employee_id, last_name
FROM employees SAMPLE (10);
```

## Вывод ora2pg (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_sampled AS SELECT employee_id, last_name
FROM employees SAMPLE(10);
```

Скопировано как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "10"
LINE 2: FROM employees SAMPLE(10);
                              ^
```

Особенность этого gap'а: у PostgreSQL **есть** эквивалентная
функциональность — `TABLESAMPLE BERNOULLI (n)` / `TABLESAMPLE SYSTEM
(n)` — но синтаксис другой, и ora2pg не делает этой замены. То есть
проблема не в отсутствии возможности, а именно в неконвертированном
синтаксисе.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/sample_clause.py`. Ручная переработка:
`SAMPLE (n)` → `TABLESAMPLE BERNOULLI (n)` (построчная выборка, ближе к
Oracle `SAMPLE`), `SAMPLE BLOCK (n)` → `TABLESAMPLE SYSTEM (n)`.
