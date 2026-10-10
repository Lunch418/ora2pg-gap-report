# GAP-017: `JSON_TABLE(...)` — не существует в PostgreSQL 16 и старше

Oracle feature: `JSON_TABLE(json_doc, path COLUMNS (...))` — табличная
проекция JSON-документа в обычные реляционные строки/столбцы прямо в
`FROM`.

## Минимальный пример

```sql
SELECT COUNT(*) INTO v_count
FROM JSON_TABLE(
    '[{"id":1,"amount":100},{"id":2,"amount":200}]',
    '$[*]'
    COLUMNS (
        id     NUMBER PATH '$.id',
        amount NUMBER PATH '$.amount'
    )
);
```

## Вывод ora2pg (v25.0, `-t PACKAGE`)

Конструкция копируется как есть — `JSON_TABLE`, `COLUMNS`, `PATH` не
переписаны ни во что.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16: `CREATE PROCEDURE` проходит без
ошибки, падает при первом вызове:

```
ERROR:  syntax error at or near "COLUMNS"
```

В PostgreSQL 16 и более ранних версиях функции `JSON_TABLE` нет вообще.
**Важная оговорка:** PostgreSQL 17 добавил `JSON_TABLE`, но с собственным
синтаксисом секции `COLUMNS` (в частности, `NESTED PATH`, размещение
`ERROR`/`DEFAULT ... ON ERROR`) — совпадение с синтаксисом Oracle не
проверялось эмпирически в этом исследовании (в песочнице доступен только
PostgreSQL 16), поэтому детектор не делает различий по целевой версии и
флагует конструкцию всегда — лучше ложное срабатывание на PG17, где
что-то может конвертироваться почти как есть, чем пропуск реального
падения на более распространённых пока версиях 16 и старше.

**Reproducible: YES (PostgreSQL 16).** Ora2Pg version: 25.0.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/json_table.py`.

## PostgreSQL 17 и 18

Проверено позже на ora2pg 25.0 и настоящих PostgreSQL 16, 17 и 18
(`tests/test_pg_version.py`, вывод записан в `tests/fixtures/pg_version/`).
ora2pg переписывает типы столбцов (`NUMBER` -> `bigint`) и оставляет
остальное; на 17 и 18 процедура загружается и возвращает то же число
строк, `NESTED PATH ... COLUMNS (...)` тоже работает. Не работает только
место обработки ошибок по Oracle - перед списком столбцов: `'$[*]' ERROR ON
ERROR COLUMNS (...)` падает с `syntax error at or near "ERROR"` -
PostgreSQL принимает `ON ERROR`/`ON EMPTY` после `COLUMNS (...)`.

Поэтому с `--pg-version 17` (или 18) простой JSON_TABLE больше не
сообщается, а с `ON ERROR`/`ON EMPTY` перед `COLUMNS` - сообщается, со
своим текстом (`json_table.on_error`): перенесите предложение за список
столбцов.
