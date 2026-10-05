# GAP-116: повторный `pkg.proc;` без скобок теряет `CALL`

Oracle feature: вызов процедуры без параметров без скобок, с именем своего
же пакета (`job_pkg.refresh;`), из другой подпрограммы того же пакета.

## Как нашли

При сведении GAP-117 к минимальному примеру: тело пакета, несколько раз
вызывающее свою же процедуру, вышло с одним сконвертированным вызовом и
следующим несконвертированным.

## Минимальный пример

```sql
CREATE OR REPLACE PACKAGE BODY job_pkg AS
  PROCEDURE refresh IS
  BEGIN
    NULL;
  END;
  PROCEDURE run_all IS
  BEGIN
    job_pkg.refresh;
    job_pkg.refresh;
  END;
END job_pkg;
/
```

Oracle 23ai компилирует и выполняет его.

## Вывод ora2pg (v25.0, `-t PACKAGE`)

```sql
CREATE OR REPLACE PROCEDURE job_pkg.run_all () AS $body$
BEGIN
    CALL job_pkg.refresh();
    job_pkg.refresh();
  END;
$body$
LANGUAGE PLPGSQL
;
```

Первый вызов получает `CALL`, второй - только скобки.

## Наблюдаемая проблема

PL/pgSQL не принимает голый вызов процедуры, поэтому подпрограмма не
загружается в PostgreSQL 16:

```
ERROR:  42601: syntax error at or near "job_pkg"
```

Что именно ломается, по отдельным прогонам того же пакета:

| В одной подпрограмме | Результат |
|---|---|
| `job_pkg.refresh;` один раз | сконвертирован |
| `refresh; job_pkg.refresh;` | второй - нет |
| `job_pkg.refresh; job_pkg.refresh;` | второй - нет |
| `refresh; refresh;` | сконвертированы |
| `job_pkg.refresh(); job_pkg.refresh();` | сконвертированы |
| `job_pkg.log_it('a'); job_pkg.log_it('b');` | сконвертированы |
| тот же вызов по одному разу в двух подпрограммах | сконвертированы |

То есть: квалифицированный вызов без скобок процедуры, которую та же
подпрограмма уже вызывала.

**Воспроизводится: ДА.** Ora2Pg 25.0, PostgreSQL 16, Oracle 23ai.

## Вердикт

**Пробел подтверждён, severity high, failure_stage deployment.** Допишите
`CALL` перед повторным вызовом в сгенерированном коде или пишите такие
вызовы в исходнике со скобками до конвертации.

Реализовано: `ora2pg_gap_report/detectors/repeated_package_call.py`.
