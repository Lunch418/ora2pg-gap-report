# GAP-021: `CREATE TYPE ... TABLE OF` / `VARRAY OF` — коллекционный тип пропадает без следа

Oracle feature: коллекционный тип (`TABLE OF` — nested table, `VARRAY(n)
OF` — varray), объявляемый на уровне схемы и затем используемый как тип
столбца в обычной таблице (или как локальный тип `TYPE ... IS TABLE OF`
внутри PL/SQL — тот случай уже отдельно покрыт GAP-003/`bulk_collect.py`;
здесь речь именно про самостоятельное объявление типа на уровне схемы).

## Минимальный пример

```sql
CREATE TYPE phone_list_t AS TABLE OF VARCHAR2(20);
/
CREATE TABLE customers (
    customer_id NUMBER,
    phones      phone_list_t
)
NESTED TABLE phones STORE AS phones_store;
```

## Вывод ora2pg (v25.0, `-t TABLE`)

```
[DEBUG] unhandled line: CREATE TYPE phone_list_t AS TABLE OF VARCHAR2(20);
```

```sql
CREATE TABLE customers (
	customer_id bigint,
	phones PHONE_LIST_T
) ;
```

Сам `CREATE TYPE` не появляется в выводе вообще — не как
`-- Unsupported`-комментарий (как для объектных типов, см. GAP-009), а
полностью, без единого следа кроме служебной строки уровня **DEBUG** в
логе. При этом столбец `phones` в сгенерированной таблице продолжает
ссылаться на тип `phone_list_t`, который так и не был создан.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 — загрузка сгенерированного
`CREATE TABLE` падает сразу же:

```
ERROR:  type "phone_list_t" does not exist
LINE 3:  phones PHONE_LIST_T
                ^
```

Это самый быстрый по времени обнаружения gap из всего реестра — ошибка
происходит уже на этапе загрузки DDL, а не при первом вызове процедуры
(как у большинства других находок, где `check_function_bodies = false`
откладывает ошибку). Отдельно проверено: `VARRAY(n) OF` ведёт себя
идентично — тоже полностью пропадает, тот же класс ошибки при загрузке
зависимой таблицы.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/collection_type.py`. Отдельно от GAP-009
(`object_type.py`, который покрывает только `AS OBJECT`/`TYPE BODY`) —
это разные варианты `CREATE TYPE` с разным характером отказа.
