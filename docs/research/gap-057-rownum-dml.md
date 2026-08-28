# GAP-057: `ROWNUM` в `UPDATE`/`DELETE` превращается в `LIMIT`

Oracle feature: ограничение числа изменяемых строк через `WHERE ROWNUM
<= n`.

## Минимальный пример

```sql
UPDATE employees SET bonus = 0 WHERE ROWNUM <= 10;
```

## Вывод ora2pg (v25.0, `-t QUERY`)

```sql
UPDATE employees SET bonus = 0 LIMIT 10;
```

Замена `ROWNUM` на `LIMIT` — правильная идея для `SELECT`, но не для
DML.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "LIMIT"
LINE 1: UPDATE employees SET bonus = 0 LIMIT 10;
                                       ^
```

То же самое для `DELETE`:

```sql
DELETE FROM employees WHERE ROWNUM <= 5;
```
```sql
DELETE FROM employees LIMIT 5;
```
```
ERROR:  syntax error at or near "LIMIT"
LINE 1: DELETE FROM employees LIMIT 5;
                              ^
```

**Важная граница детектора.** `ROWNUM` во вложенном подзапросе
конвертируется корректно и работает — проверено отдельно:

```sql
DELETE FROM employees WHERE emp_id IN (SELECT emp_id FROM staff WHERE ROWNUM <= 5);
```
```sql
DELETE FROM employees WHERE emp_id IN (SELECT emp_id FROM staff LIMIT 5);
```
```
DELETE 0
```

`LIMIT` внутри подзапроса — совершенно нормальный PostgreSQL. Поэтому
детектор помечает `ROWNUM` только тогда, когда ближайшее
предшествующее ключевое слово оператора — `UPDATE` или `DELETE`, а не
`SELECT`. Это не эвристика «на всякий случай», а прямое следствие
измеренного поведения.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/rownum_dml.py`. Ручная переработка: через
подзапрос по первичному ключу — `DELETE FROM t WHERE id IN (SELECT id
FROM t WHERE ... LIMIT n)`. Смысл при этом всё равно меняется: Oracle не
обещает, какие именно n строк попадут под `ROWNUM`, поэтому во
внутренний `SELECT` почти всегда нужно дописать явный `ORDER BY`, иначе
выбор строк останется недетерминированным.
