# GAP-066: `CREATE VIEW ... WITH READ ONLY`

Oracle feature: представление, через которое запрещено менять данные —
`INSERT`/`UPDATE`/`DELETE` по нему падают с ORA-42399.

## Минимальный пример

```sql
CREATE OR REPLACE VIEW v_emp AS
  SELECT emp_id, name FROM employees
  WITH READ ONLY;
```

## Вывод ora2pg (v25.0, `-t VIEW`)

```sql
CREATE OR REPLACE VIEW v_emp AS SELECT emp_id, name FROM employees;
```

Оговорка просто выброшена.

## Наблюдаемая проблема

Ошибки нет ни на загрузке, ни потом. Простое представление в PostgreSQL
по умолчанию автоматически обновляемое, поэтому запись через него молча
проходит. Подтверждено на реальном PostgreSQL 16:

```
INSERT 0 1
 emp_id |               name
--------+----------------------------------
    999 | written through a READ ONLY view
(1 row)
```

Строка действительно попала в базовую таблицу. Защита, объявленная в
Oracle в самом определении объекта, после миграции исчезает бесследно —
это `failure_stage = semantic`.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/read_only_view.py`. Ручная переработка:
вернуть запрет явно — либо правами (`REVOKE INSERT, UPDATE, DELETE ON
<view> FROM ...`), либо триггером `INSTEAD OF`, возбуждающим исключение.
Родственный gap про таблицы — GAP-026/`read_only_table.py`.
