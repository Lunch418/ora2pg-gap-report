*English | [Русский](builtin-packages.ru.md)*

# DBMS_* and UTL_* calls

Covers: the `dbms_utl_calls` classifier (no GAP number of its own: it
flags every call into Oracle's built-in packages that `ora2pg` does not
convert).

## The problem

Oracle code leans on its built-in packages for output, timing, LOBs,
dynamic SQL, files, HTTP and mail. `ora2pg` converts some calls and copies
the rest as they are; those fail at the first call. Most have a direct
PostgreSQL equivalent, some belong outside the database, and the `orafce`
extension emulates a good part of the rest if you would rather not touch
the calls at all.

## Direct equivalents

Each line of this block is checked against a real PostgreSQL 16:

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
    -- DBMS_LOB.SUBSTR(v_lob, 5, 8): amount first, offset second ...
    -- ... substr() takes them the other way round: offset, then length
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

    -- DBMS_UTILITY.GET_TIME (hundredths of a second)
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
| `DBMS_LOB.CREATETEMPORARY`, `FREETEMPORARY` | nothing: `text`/`bytea` are plain values |
| `DBMS_UTILITY.FORMAT_ERROR_STACK` | `SQLERRM` |
| `DBMS_UTILITY.FORMAT_ERROR_BACKTRACE`, `FORMAT_CALL_STACK` | `GET STACKED DIAGNOSTICS ... PG_EXCEPTION_CONTEXT`, `GET DIAGNOSTICS ... PG_CONTEXT` |
| `DBMS_UTILITY.GET_TIME` | `clock_timestamp()` (or the formula above) |
| `DBMS_APPLICATION_INFO.SET_MODULE/SET_ACTION` | `set_config('application_name', ...)` |
| `DBMS_ASSERT.ENQUOTE_NAME`, `ENQUOTE_LITERAL` | `quote_ident`, `quote_literal`; in dynamic SQL, `format('%I', ...)` and `%L` |
| `DBMS_CRYPTO.HASH` | `sha256()`, `sha512()`, `md5()`; `pgcrypto`'s `digest()` for others |
| `UTL_RAW.CAST_TO_RAW` / `CAST_TO_VARCHAR2` | `convert_to(t, 'UTF8')` / `convert_from(b, 'UTF8')` |
| `UTL_ENCODE.BASE64_ENCODE` / `DECODE` | `encode(b, 'base64')` / `decode(t, 'base64')` |
| `DBMS_STATS.GATHER_TABLE_STATS` | `ANALYZE table` |
| `DBMS_MVIEW.REFRESH` | `REFRESH MATERIALIZED VIEW [CONCURRENTLY] mv` |

## Dynamic SQL: DBMS_SQL and EXECUTE IMMEDIATE

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

`DBMS_SQL`'s cursor-by-cursor API (open, parse, bind, define column,
execute, fetch, close) collapses into `EXECUTE ... INTO ... USING`, or
`FOR r IN EXECUTE ... LOOP` for many rows. Bind values with `USING`
(`$1`, `$2`) and quote names with `format('%I')`, never by concatenating
input into the string.

## Belongs outside the database

| Oracle | Where it goes |
|---|---|
| `DBMS_SCHEDULER`, `DBMS_JOB` | the `pg_cron` extension, or the scheduler you already run (cron, systemd timers, the application) |
| `UTL_HTTP`, `UTL_SMTP`, `UTL_MAIL` | a job table filled in the transaction and a worker outside the database that sends; extensions exist (`http`), but a slow remote server then holds your transaction open |
| `UTL_FILE` | the application, or `COPY ... TO/FROM` and `pg_read_file()` on the server (superuser or the `pg_read_server_files`/`pg_write_server_files` roles) |
| `DBMS_PIPE`, `DBMS_ALERT` | `LISTEN`/`NOTIFY` |
| `DBMS_METADATA.GET_DDL` | `pg_get_functiondef()`, `pg_get_viewdef()`, `pg_get_indexdef()`, `pg_get_constraintdef()`; a whole table's DDL only from `pg_dump --schema-only` |

## orafce: keep the calls

The `orafce` extension implements `DBMS_OUTPUT`, `DBMS_PIPE`,
`DBMS_ALERT`, `UTL_FILE`, `DBMS_RANDOM`, `DBMS_UTILITY` (parts), plus
Oracle functions such as `NVL2`, `ADD_MONTHS` and `TRUNC(date)`, under the
same names. It is a fast way to get a large codebase running. The calls
then depend on an extension your PostgreSQL provider must offer, and its
behaviour is an emulation: test the calls that matter, `DBMS_OUTPUT` in
particular, which buffers like Oracle's and prints nothing unless the
client asks for it.
