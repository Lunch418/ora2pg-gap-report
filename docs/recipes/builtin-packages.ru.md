*[English](builtin-packages.md) | Русский*

# Вызовы DBMS_* и UTL_*

Покрывает: классификатор `dbms_utl_calls` (своего номера GAP у него нет: он
отмечает каждый вызов встроенных пакетов Oracle, который `ora2pg` не
конвертирует).

## Проблема

Код Oracle опирается на встроенные пакеты для вывода, замеров времени,
LOB, динамического SQL, файлов, HTTP и почты. Часть вызовов `ora2pg`
конвертирует, остальные копирует как есть, и они падают при первом
вызове. У большинства есть прямой аналог в PostgreSQL, часть должна жить
вне базы, а значительную долю остального эмулирует расширение `orafce`,
если вызовы трогать совсем не хочется.

## Прямые аналоги

Каждая строка этого блока проверена на настоящем PostgreSQL 16:

```sql
DO $$
DECLARE
    v_lob   text := 'Hello, PostgreSQL';
    v_bytes bytea;
BEGIN
    -- DBMS_OUTPUT.PUT_LINE('x')
    RAISE NOTICE 'x';

    -- DBMS_LOB.GETLENGTH(v_lob)
    ASSERT length(v_lob) = 17;
    -- DBMS_LOB.SUBSTR(v_lob, 5, 8): сначала количество, потом смещение ...
    -- ... а substr() принимает наоборот: смещение, потом длину
    ASSERT substr(v_lob, 8, 5) = 'Postg';
    -- DBMS_LOB.INSTR(v_lob, 'Post')
    ASSERT strpos(v_lob, 'Post') = 8;
    -- DBMS_LOB.APPEND(v_lob, '!')
    v_lob := v_lob || '!';
    ASSERT right(v_lob, 1) = '!';

    -- UTL_RAW.CAST_TO_RAW / UTL_RAW.CAST_TO_VARCHAR2
    v_bytes := convert_to('abc', 'UTF8');
    ASSERT convert_from(v_bytes, 'UTF8') = 'abc';
    -- UTL_ENCODE.BASE64_ENCODE
    ASSERT encode(v_bytes, 'base64') = 'YWJj';
    -- DBMS_CRYPTO.HASH(..., DBMS_CRYPTO.HASH_SH256)
    ASSERT encode(sha256(v_bytes), 'hex') = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad';

    -- DBMS_ASSERT.ENQUOTE_NAME / ENQUOTE_LITERAL
    ASSERT quote_ident('Mixed Case') = '"Mixed Case"';
    ASSERT quote_literal('O''Brien') = '''O''''Brien''';

    -- DBMS_RANDOM.VALUE(10, 20)
    ASSERT (SELECT bool_and(v >= 10 AND v < 20) FROM (SELECT 10 + random() * 10 AS v FROM generate_series(1, 100)) s);

    -- DBMS_UTILITY.GET_TIME (сотые доли секунды)
    ASSERT (extract(epoch FROM clock_timestamp()) * 100)::bigint > 0;

    -- DBMS_APPLICATION_INFO.SET_MODULE('billing', 'close month')
    PERFORM set_config('application_name', 'billing: close month', true);
    ASSERT current_setting('application_name') = 'billing: close month';
END $$;

-- DBMS_LOCK.SLEEP(0.1) / DBMS_SESSION.SLEEP(0.1)
SELECT pg_sleep(0.1);
```

| Oracle | PostgreSQL |
|---|---|
| `DBMS_OUTPUT.PUT_LINE(x)` | `RAISE NOTICE '%', x` |
| `DBMS_LOCK.SLEEP(n)`, `DBMS_SESSION.SLEEP(n)` | `pg_sleep(n)` |
| `DBMS_RANDOM.VALUE`, `VALUE(lo, hi)` | `random()`, `lo + random() * (hi - lo)` |
| `DBMS_LOB.GETLENGTH`, `SUBSTR(l, n, off)`, `INSTR`, `APPEND` | `length`, `substr(l, off, n)`, `strpos`, `\|\|` |
| `DBMS_LOB.CREATETEMPORARY`, `FREETEMPORARY` | ничего: `text`/`bytea` - обычные значения |
| `DBMS_UTILITY.FORMAT_ERROR_STACK` | `SQLERRM` |
| `DBMS_UTILITY.FORMAT_ERROR_BACKTRACE`, `FORMAT_CALL_STACK` | `GET STACKED DIAGNOSTICS ... PG_EXCEPTION_CONTEXT`, `GET DIAGNOSTICS ... PG_CONTEXT` |
| `DBMS_UTILITY.GET_TIME` | `clock_timestamp()` (или формула выше) |
| `DBMS_APPLICATION_INFO.SET_MODULE/SET_ACTION` | `set_config('application_name', ...)` |
| `DBMS_ASSERT.ENQUOTE_NAME`, `ENQUOTE_LITERAL` | `quote_ident`, `quote_literal`; в динамическом SQL - `format('%I', ...)` и `%L` |
| `DBMS_CRYPTO.HASH` | `sha256()`, `sha512()`, `md5()`; для остальных `digest()` из `pgcrypto` |
| `UTL_RAW.CAST_TO_RAW` / `CAST_TO_VARCHAR2` | `convert_to(t, 'UTF8')` / `convert_from(b, 'UTF8')` |
| `UTL_ENCODE.BASE64_ENCODE` / `DECODE` | `encode(b, 'base64')` / `decode(t, 'base64')` |
| `DBMS_STATS.GATHER_TABLE_STATS` | `ANALYZE таблица` |
| `DBMS_MVIEW.REFRESH` | `REFRESH MATERIALIZED VIEW [CONCURRENTLY] mv` |

## Динамический SQL: DBMS_SQL и EXECUTE IMMEDIATE

```sql
CREATE TABLE dyn_target (id integer, label text);

DO $$
DECLARE
    v_table text := 'dyn_target';
    v_count integer;
BEGIN
    -- EXECUTE IMMEDIATE 'INSERT INTO ' || v_table || ' VALUES (:1, :2)' USING 1, 'one';
    EXECUTE format('INSERT INTO %I VALUES ($1, $2)', v_table) USING 1, 'one';
    -- DBMS_SQL.OPEN_CURSOR / PARSE / BIND_VARIABLE / EXECUTE / FETCH_ROWS ...
    EXECUTE format('SELECT count(*) FROM %I WHERE label = $1', v_table) INTO v_count USING 'one';
    ASSERT v_count = 1;
END $$;
```

Покурсорный интерфейс `DBMS_SQL` (открыть, разобрать, привязать,
определить столбец, выполнить, выбрать, закрыть) сворачивается в
`EXECUTE ... INTO ... USING`, а для многих строк - в
`FOR r IN EXECUTE ... LOOP`. Значения передавайте через `USING` (`$1`,
`$2`), имена экранируйте через `format('%I')` и никогда не склеивайте
входные данные со строкой команды.

## Что должно жить вне базы

| Oracle | Куда это переносить |
|---|---|
| `DBMS_SCHEDULER`, `DBMS_JOB` | расширение `pg_cron` или планировщик, который у вас уже есть (cron, таймеры systemd, приложение) |
| `UTL_HTTP`, `UTL_SMTP`, `UTL_MAIL` | таблица заданий, заполняемая в транзакции, и обработчик вне базы, который отправляет; расширения есть (`http`), но тогда медленный удалённый сервер держит вашу транзакцию открытой |
| `UTL_FILE` | приложение или `COPY ... TO/FROM` и `pg_read_file()` на сервере (суперпользователь или роли `pg_read_server_files`/`pg_write_server_files`) |
| `DBMS_PIPE`, `DBMS_ALERT` | `LISTEN`/`NOTIFY` |
| `DBMS_METADATA.GET_DDL` | `pg_get_functiondef()`, `pg_get_viewdef()`, `pg_get_indexdef()`, `pg_get_constraintdef()`; DDL целой таблицы - только через `pg_dump --schema-only` |

## orafce: оставить вызовы как есть

Расширение `orafce` реализует `DBMS_OUTPUT`, `DBMS_PIPE`, `DBMS_ALERT`,
`UTL_FILE`, `DBMS_RANDOM`, часть `DBMS_UTILITY`, а также функции Oracle
вроде `NVL2`, `ADD_MONTHS` и `TRUNC(date)` под теми же именами. Это быстрый
способ запустить большую кодовую базу. Но тогда вызовы зависят от
расширения, которое должен предоставлять ваш поставщик PostgreSQL, а его
поведение - эмуляция: проверьте важные вызовы, особенно `DBMS_OUTPUT`,
который буферизует вывод, как в Oracle, и ничего не печатает, пока клиент
об этом не попросит.
