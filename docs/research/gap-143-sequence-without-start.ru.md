# GAP-143: последовательность без START WITH

Возможность Oracle: `START WITH` необязателен; последовательность начинается с MINVALUE (1), а убывающая - с MAXVALUE (-1).

## Как найдено

Прогон --migrate --load-check на чужом коде (utPLSQL, OraOpenSource Logger, библиотека Alexandria PL/SQL, демо-схемы Oracle) и разбор ошибок, которые не объяснял ни один известный пробел.

## Минимальный пример

`tests/fixtures/corpus_gaps/oracle_sequences.sql`, VALID в живом Oracle 23ai:

```sql
CREATE SEQUENCE gx_cs1 CACHE 100;
CREATE SEQUENCE gx_cs2;
CREATE SEQUENCE gx_cs3 START WITH 5 CACHE 20;
```

## Вывод ora2pg (v25.0)

```sql
CREATE SEQUENCE gx_cs INCREMENT 1 NO MINVALUE NO MAXVALUE START ;
CREATE SEQUENCE gx_cs1 INCREMENT 1 NO MINVALUE NO MAXVALUE START  CACHE 100;
CREATE SEQUENCE gx_cs3 INCREMENT 1 NO MINVALUE NO MAXVALUE START 5 CACHE 20;
```

В файловом режиме значение START остаётся пустым, а без единой опции `gx_cs2` ещё и теряет последнюю цифру и становится `gx_cs`.

## Наблюдаемая проблема

Ни одна не загружается:

```
ERROR:  syntax error at or near ";"
ERROR:  syntax error at or near "CACHE"
```

Найдено во всех четырёх последовательностях utPLSQL (`create sequence ut_suite_cache_seq /* лицензия */ cache 100;`).

**Воспроизводится: ДА.** Версия Ora2Pg: 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** `--prepare` дописывает START WITH, который подразумевает Oracle (`prepare_oracle_sequence_start`); ora2pg тогда пишет `START 1` и не портит имя, проверено: последовательности возвращают 1, 1 и 5, как в Oracle. Исправление по выводу не вернуло бы обрезанное имя, поэтому оно в исходнике.

Реализовано: `ora2pg_gap_report/detectors/sequence_without_start.py`.
