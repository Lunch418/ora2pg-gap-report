# GAP-122: процедура поставляемого пакета, вызванная как оператор, теряет `CALL`

Возможность Oracle: процедура поставляемого пакета Oracle, вызванная как
оператор - `DBMS_APPLICATION_INFO.SET_MODULE('m', 'a');`,
`DBMS_STATS.GATHER_TABLE_STATS(USER, 'GX_EMP');`, `UTL_FILE.FCLOSE_ALL;`,
`HTP.P('x');`, `OWA_UTIL.MIME_HEADER('text/plain');`,
`DBMS_OUTPUT.DISABLE;`.

## Как найден

`--migrate --load-check docker` на примерах пакетов: `display_output` из
OraOpenSource Logger падал с `syntax error at or near "htp"`, и ни один
gap этого не объяснял. В примерах ещё 30 таких вызовов (`DBMS_LOB`,
`UTL_FILE`, `DBMS_SESSION` в `file_util_pkg`, `sql_util_pkg`, Logger); их
подпрограммы падают раньше на других ошибках, потому что PostgreSQL
сообщает только первую.

## Минимальный пример

`tests/fixtures/gaps_120_123/calls_source.sql` (`gx_ext_pkg`):

```sql
CREATE OR REPLACE PACKAGE BODY gx_ext_pkg AS
  PROCEDURE run_it IS
  BEGIN
    DBMS_OUTPUT.PUT_LINE('a');
    DBMS_SESSION.SLEEP(0);
    DBMS_APPLICATION_INFO.SET_MODULE('m', 'a');
    DBMS_APPLICATION_INFO.SET_ACTION('x');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'GX_EMP');
    DBMS_SCHEDULER.RUN_JOB('J1');
    UTL_FILE.FCLOSE_ALL;
    gx_out_pkg.note('x');
    HTP.P('x');
    OWA_UTIL.MIME_HEADER('text/plain');
    DBMS_UTILITY.EXEC_DDL_STATEMENT('x');
  END;
END gx_ext_pkg;
/
```

В живом Oracle 23ai - VALID.

## Вывод ora2pg (v25.0, `-t PACKAGE`)

```sql
BEGIN
    RAISE NOTICE 'a';
    pg_sleep(0);
    DBMS_APPLICATION_INFO.SET_MODULE('m', 'a');
    DBMS_APPLICATION_INFO.SET_ACTION('x');
    DBMS_STATS.GATHER_TABLE_STATS(USER, 'GX_EMP');
    DBMS_SCHEDULER.RUN_JOB('J1');
    UTL_FILE.FCLOSE_ALL;
    gx_out_pkg.note('x');
    HTP.P('x');
    OWA_UTIL.MIME_HEADER('text/plain');
    DBMS_UTILITY.EXEC_DDL_STATEMENT('x');
  END;
```

ora2pg пишет `CALL pkg.proc(...)` только для процедур пакетов из того же
запуска: если `gx_out_pkg` есть во входе, вызов становится `CALL
gx_out_pkg.note('x')`, если нет - остаётся голым, как остальные.
`DBMS_OUTPUT.PUT_LINE` становится `RAISE NOTICE`, `DBMS_OUTPUT.ENABLE`
комментируется, а `DBMS_OUTPUT.DISABLE` копируется. В триггерах то же
самое.

## Наблюдаемая проблема

В PL/pgSQL нет голого вызова процедуры, и PostgreSQL 16 отвергает всю
подпрограмму при загрузке - есть ли замена пакету или нет:

```
ERROR:  42601: syntax error at or near "DBMS_APPLICATION_INFO"
```

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Замените
каждый вызов аналогом PostgreSQL - `CALL`/`PERFORM` своей реализации,
`set_config('application_name', ...)`, `ANALYZE`, расширение вроде
orafce - или уберите его. После этого фикстура загружается, и `CALL
gx_ext_pkg.run_it()` выполняется (`tests/test_gaps_120_123_load.py`).

Не сообщается: то, что ora2pg на уровне операторов конвертирует (печать и
ENABLE из DBMS_OUTPUT, последовательность open/parse/execute из DBMS_SQL,
DBMS_STANDARD), SLEEP (GAP-123) и вызовы функций внутри выражений (`n :=
DBMS_RANDOM.VALUE`). `dbms_utl_calls` продолжает сообщать о таких
использованиях; о вызовах-операторах из этого gap'а он больше не
сообщает. У вызова пользовательского пакета вне конвертируемого входа та
же проблема, но по одному файлу нельзя понять, какие пакеты во входе
есть; `--migrate` конвертирует их все за один запуск, так что для него
проблема только в поставляемых пакетах.

Реализовано: `ora2pg_gap_report/detectors/supplied_package_call.py`.
