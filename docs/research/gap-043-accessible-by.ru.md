# GAP-043: `ACCESSIBLE BY` — белый список вызывающих

Oracle feature: `ACCESSIBLE BY (...)` (12c+) — подпрограмма объявляется
доступной только перечисленным пакетам/процедурам/функциям; остальные
получают ошибку компиляции при попытке вызова. Средство инкапсуляции
внутри одной схемы, поверх обычных `GRANT`.

## Минимальный пример

```sql
CREATE OR REPLACE PROCEDURE secret_proc (p_id NUMBER)
  ACCESSIBLE BY (PACKAGE hr_admin_pkg)
IS
BEGIN
  UPDATE employees SET salary = salary * 1.1 WHERE employee_id = p_id;
END;
/
```

## Вывод ora2pg (v25.0, `-t PROCEDURE`)

```sql
CREATE OR REPLACE PROCEDURE secret_proc (p_id bigint) ACCESSIBLE BY (PACKAGE hr_admin_pkg) AS $body$
BEGIN
  UPDATE employees SET salary = salary * 1.1 WHERE employee_id = p_id;
END;
$body$
LANGUAGE PLPGSQL
;
```

Секция перенесена дословно прямо в заголовок функции.

## Наблюдаемая проблема

Подтверждено на реальном PostgreSQL 16 — падает при загрузке, то есть
процедура не создаётся вообще:

```
ERROR:  syntax error at or near "ACCESSIBLE"
LINE 1: ...TE OR REPLACE PROCEDURE secret_proc (p_id bigint) ACCESSIBLE...
                                                             ^
```

**Reproducible: YES.** Ora2Pg version: 25.0, PostgreSQL 16.

## Вердикт

**Gap подтверждён.** Реализовано:
`ora2pg_gap_report/detectors/accessible_by.py`. Прямого аналога в
PostgreSQL нет: ограничение «какой именно код может вызвать» не
выражается. Ближайшее по смыслу — вынести подпрограмму в отдельную схему
и раздать права `GRANT`/`REVOKE`, что даёт защиту на уровне ролей, а не
конкретных вызывающих подпрограмм.
