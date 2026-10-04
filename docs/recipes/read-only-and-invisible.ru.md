*[English](read-only-and-invisible.md) | Русский*

# Таблицы и представления только для чтения, невидимые столбцы и индексы

Покрывает: GAP-026 (`read_only_table`), GAP-066 (`read_only_view`), GAP-020
(`invisible_column`), GAP-025 (`invisible_index`).

## Проблема

Четыре гарантии Oracle, которые `ora2pg` молча теряет, потому что в
PostgreSQL для них нет ключевого слова. После миграции ничего не падает,
гарантии просто больше нет:

- `ALTER TABLE ... READ ONLY`: запись начинает проходить (GAP-026).
- `CREATE VIEW ... WITH READ ONLY`: простое представление в PostgreSQL по
  умолчанию обновляемое, и запись через него доходит до таблицы (GAP-066).
- Столбец `INVISIBLE` появляется в `SELECT *` и в `INSERT` без списка
  столбцов (GAP-020).
- Индекс `INVISIBLE` снова используется планировщиком (GAP-025).

## Таблица только для чтения: триггер и права

Одних прав мало: владелец и суперпользователи их обходят. `READ ONLY` в
Oracle останавливает всех, триггер тоже:

```sql
CREATE TABLE rates (currency text PRIMARY KEY, rate numeric NOT NULL);
INSERT INTO rates VALUES ('EUR', 1.08);

CREATE FUNCTION forbid_writes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'table % is read-only', TG_TABLE_NAME
        USING ERRCODE = 'read_only_sql_transaction';
END;
$$;

-- ALTER TABLE rates READ ONLY;
CREATE TRIGGER rates_read_only
    BEFORE INSERT OR UPDATE OR DELETE OR TRUNCATE ON rates
    FOR EACH STATEMENT EXECUTE FUNCTION forbid_writes();

DO $$
BEGIN
    BEGIN
        UPDATE rates SET rate = 2;
        RAISE EXCEPTION 'обновление прошло';
    EXCEPTION WHEN read_only_sql_transaction THEN
        NULL;  -- так и должно быть
    END;
    ASSERT (SELECT rate FROM rates) = 1.08;
END $$;
```

`ALTER TABLE ... READ WRITE` тогда превращается в `ALTER TABLE rates
DISABLE TRIGGER rates_read_only` (и `ENABLE`, чтобы вернуть). Заодно
отзовите `INSERT`, `UPDATE`, `DELETE` и `TRUNCATE` у ролей приложения,
чтобы намерение было видно и в правах.

## Представление только для чтения

```sql
-- CREATE VIEW eur_rate AS SELECT ... WITH READ ONLY;
CREATE VIEW eur_rate AS SELECT currency, rate FROM rates WHERE currency = 'EUR';

CREATE FUNCTION forbid_view_writes()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'view % is read-only', TG_TABLE_NAME
        USING ERRCODE = 'read_only_sql_transaction';
END;
$$;

CREATE TRIGGER eur_rate_read_only
    INSTEAD OF INSERT OR UPDATE OR DELETE ON eur_rate
    FOR EACH ROW EXECUTE FUNCTION forbid_view_writes();

DO $$
BEGIN
    BEGIN
        DELETE FROM eur_rate;
        RAISE EXCEPTION 'удаление прошло';
    EXCEPTION WHEN read_only_sql_transaction THEN
        NULL;  -- так и должно быть
    END;
END $$;
```

Триггер `INSTEAD OF` перехватывает любую запись в представление, так что до
таблицы ничего не доходит, в том числе у владельца. Если вам достаточно
выдать на представление только `SELECT` всем, кроме владельца, права
справятся и без триггера.

## Невидимый столбец: представление поверх таблицы

Оставьте таблицу под другим именем, а старое имя отдайте представлению,
в котором этого столбца нет. Программы, которые используют `SELECT *` или
`INSERT` без списка столбцов, видят ровно то же, что видели в Oracle; код,
который знает о столбце, работает с таблицей.

```sql
-- CREATE TABLE customers (id ..., name ..., legacy_code ... INVISIBLE);
CREATE TABLE customers_all (
    id          integer PRIMARY KEY,
    name        text NOT NULL,
    legacy_code text
);
CREATE VIEW customers AS SELECT id, name FROM customers_all;

INSERT INTO customers VALUES (1, 'Acme');   -- без списка столбцов, как раньше
UPDATE customers_all SET legacy_code = 'X1' WHERE id = 1;

DO $$
BEGIN
    ASSERT (SELECT count(*) FROM information_schema.columns
            WHERE table_name = 'customers') = 2;           -- SELECT * показывает два
    ASSERT (SELECT legacy_code FROM customers_all WHERE id = 1) = 'X1';
END $$;
```

Представление, которое выбирает простые столбцы из одной таблицы, в
PostgreSQL обновляемое: `INSERT`, `UPDATE` и `DELETE` через него доходят до
таблицы, а скрытый столбец получает значение по умолчанию.

## Невидимый индекс

В PostgreSQL нельзя поддерживать индекс в актуальном состоянии так, чтобы
планировщик его не замечал. Что делать, зависит от того, зачем он был
невидимым:

- **Его проверяли перед удалением.** Решите сейчас: удалить или оставить
  обычным индексом. Чтобы сначала посмотреть план без него, удалите его в
  транзакции и откатите (`BEGIN; DROP INDEX ...; EXPLAIN ...; ROLLBACK;`);
  учтите, что `DROP INDEX` блокирует таблицу до отката, поэтому делайте это
  на копии или на ненагруженной системе.
- **Его готовили к включению.** Создайте его тогда, когда планировщику
  пора им пользоваться. Расширение `hypopg` показывает, использовал бы план
  индекс, не создавая его.
- Не правьте `pg_index.indisvalid` вручную, чтобы изобразить невидимость:
  это вмешательство в каталог, которого не ожидают ни планировщик, ни
  `pg_dump`.
