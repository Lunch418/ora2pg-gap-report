# GAP-056: `FOR UPDATE ... WAIT n`

Oracle feature: блокировка строк с ожиданием не дольше n секунд.

## Минимальный пример

```sql
SELECT * FROM accounts WHERE id = 1 FOR UPDATE OF bal WAIT 5;
```

## Вывод ora2pg (v25.0, `-t QUERY`)

```sql
SELECT * FROM accounts WHERE id = 1 FOR UPDATE OF bal WAIT 5;
```

Скопировано как есть.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16:

```
ERROR:  syntax error at or near "WAIT"
LINE 1: ...ELECT * FROM accounts WHERE id = 1 FOR UPDATE OF bal WAIT 5;
                                                                ^
```

У `FOR UPDATE` в PostgreSQL есть только `NOWAIT` и `SKIP LOCKED` —
варианта «подожди ровно n секунд» нет. `NOWAIT` пишется одинаково в
обеих СУБД и переносится корректно, поэтому детектор помечает только
форму с числовым таймаутом.

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/for_update_wait.py`. Ручная переработка:
эквивалент задаётся на уровне сессии, а не запроса — `SET LOCAL
lock_timeout = 'n s'` перед `SELECT ... FOR UPDATE`. Разница не только в
синтаксисе: по истечении времени Oracle возвращает ORA-30006, а
PostgreSQL прерывает запрос по `lock_timeout`, так что обработку ошибки
в вызывающем коде тоже нужно поправить.
