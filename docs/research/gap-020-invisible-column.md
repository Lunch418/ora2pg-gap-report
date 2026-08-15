# GAP-020: столбец `INVISIBLE` теряет своё скрытие

Oracle feature: `INVISIBLE` — модификатор столбца, исключающий его из
`SELECT *` и из позиционного `INSERT` без явного списка столбцов; столбец
по-прежнему доступен, но только при явном упоминании по имени. Частый
сценарий использования — добавление нового столбца в существующую
таблицу без риска сломать старый код, полагающийся на прежний состав
`SELECT *`.

## Минимальный пример

```sql
CREATE TABLE customers (
    customer_id NUMBER,
    legacy_code VARCHAR2(10) INVISIBLE
);
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```sql
CREATE TABLE customers (
	customer_id bigint,
	legacy_code varchar(10)
) ;
```

Модификатор `INVISIBLE` пропадает без следа — столбец конвертируется как
обычный, видимый.

## Наблюдаемая проблема

Не синтаксическая ошибка — `CREATE TABLE` выполняется без проблем. У
PostgreSQL нет аналога `INVISIBLE` вообще, так что поведение молча
меняется: подтверждено на реальном PostgreSQL 16 —

```sql
INSERT INTO customers VALUES (1, 'x');
SELECT * FROM customers;
-- customer_id | legacy_code
-- ------------+-------------
--           1 | x
```

`legacy_code` появляется в `SELECT *`, хотя в Oracle он был бы из него
исключён. Для типичного сценария использования `INVISIBLE` (скрыть новый
столбец от старого кода) это именно тот случай, который модификатор
должен был предотвратить — старый код, делающий `SELECT *`, после
миграции неожиданно получает лишний столбец.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/invisible_column.py`. Покрывает только
`CREATE TABLE`; `ALTER TABLE ... MODIFY (col INVISIBLE)` на существующей
таблице пока не отслеживается.
