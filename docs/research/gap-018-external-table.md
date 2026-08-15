# GAP-018: `CREATE TABLE ... ORGANIZATION EXTERNAL` — секция полностью отбрасывается

Oracle feature: внешняя таблица (`ORGANIZATION EXTERNAL`) — таблица, чьи
данные физически хранятся не в БД, а во внешнем файле (обычно через
`ORACLE_LOADER`), и читаются оттуда при каждом обращении.

## Минимальный пример

```sql
CREATE TABLE ext_orders (
    order_id NUMBER,
    amount   NUMBER
)
ORGANIZATION EXTERNAL (
    TYPE ORACLE_LOADER
    DEFAULT DIRECTORY ext_dir
    ACCESS PARAMETERS (
        RECORDS DELIMITED BY NEWLINE
        FIELDS TERMINATED BY ','
    )
    LOCATION ('orders.csv')
)
REJECT LIMIT UNLIMITED;
```

## Вывод ora2pg (v25.0, `-t TABLE`, и отдельно `--estimate_cost -t TABLE`)

```sql
CREATE TABLE ext_orders (
	order_id bigint,
	amount bigint
) ;
```

Вся секция `ORGANIZATION EXTERNAL` (`TYPE`/`DEFAULT DIRECTORY`/
`ACCESS PARAMETERS`/`LOCATION`/`REJECT LIMIT`) исчезает без следа —
таблица создаётся как обычная, физически хранимая. Ни ошибки, ни
предупреждения — включая `--estimate_cost`, который тоже никак не
отмечает эту таблицу.

## Наблюдаемая проблема

Это не синтаксическая ошибка — `CREATE TABLE` выполняется без проблем.
Но результат принципиально другой: единственный источник данных этой
таблицы (внешний файл) исчезает полностью. Таблица создаётся пустой и
никогда не подхватит содержимое `orders.csv` — а поскольку `CREATE
TABLE` не падает и не предупреждает, при реальной миграции это легко
не заметить, пока приложение не начнёт получать пустые результаты там,
где раньше были строки из файла.

Ближайший эквивалент в PostgreSQL — foreign table через `file_fdw` (или
конкретный fdw под нужный формат) — настраивается вручную, полностью
отдельным путём от обычного `CREATE TABLE`.

**Reproducible: YES.** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/external_table.py`. Поиск
`ORGANIZATION EXTERNAL` ограничен текстом конкретного `CREATE TABLE`
(до его завершающей `;`) — тот же подход, что и в
`table_partitioning.py`, чтобы не приписать находку случайной
несвязанной таблице по файлу.
