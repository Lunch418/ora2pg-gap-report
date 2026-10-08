# GAP-123: `DBMS_LOCK.SLEEP` становится `pg_sleep(n);` без `PERFORM`

Возможность Oracle: `DBMS_LOCK.SLEEP(n)` или, начиная с 18c,
`DBMS_SESSION.SLEEP(n)`, вызванные как оператор.

## Как найден

При сведении GAP-122 к минимальному случаю: первой ошибкой оказался не
вызов поставляемого пакета, а строка, которую ora2pg конвертировал.

## Минимальный пример

`tests/fixtures/gaps_120_123/edge_source.sql`:

```sql
    SYS.DBMS_SESSION.SLEEP(0.1);
    IF c IS NULL THEN DBMS_SESSION.SLEEP(1); END IF;
```

в процедуре пакета и `DBMS_SESSION.SLEEP(0);` в триггере. В живом Oracle
23ai - VALID.

## Вывод ora2pg (v25.0, `-t PACKAGE`, `-t TRIGGER`)

```sql
    pg_sleep(0.1);
    IF c IS NULL THEN pg_sleep(1);END IF;
```

В `Ora2Pg/PLSQL.pm` у ora2pg два правила для этого вызова.
`plsql_to_plpgsql` пишет `PERFORM pg_sleep`, `replace_oracle_function` -
голый `pg_sleep`, и срабатывает раньше, так что правило с PERFORM
`DBMS_LOCK.SLEEP` уже не видит.

## Наблюдаемая проблема

PL/pgSQL не принимает вызов функции как оператор без `PERFORM`:

```
ERROR:  42601: syntax error at or near "pg_sleep"
```

и подпрограмма или функция триггера не загружается.

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Gap подтверждён, severity high, failure_stage deployment.** Механически:
`PERFORM pg_sleep(n);`. Это делает `--fix` (`fix_bare_pg_sleep` в
`ora2pg_gap_report/autofix.py`), а `--load-check` сообщает ошибку как
исправимую. `--migrate` его применяет.

Реализовано: `ora2pg_gap_report/detectors/dbms_sleep.py`.
