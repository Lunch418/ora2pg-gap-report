# Реестр подтверждённых gap'ов

Каждая строка — конкретная Oracle-конструкция, для которой эмпирически
подтверждено (не предположено), что `ora2pg` конвертирует её некорректно
или пропускает без предупреждения. См. «Методология» в основном
[README](../../README.md) — детектор появляется только после того, как
гипотеза прошла этот цикл; отклонённые гипотезы в реестр не попадают (они
задокументированы в `step0-show-report-baseline.md`, разделы 1 и частично
4, как явно отклонённые).

Номера присвоены в порядке документирования, не в порядке значимости или
хронологии реализации — GAP-002/003 были задокументированы раньше
GAP-001/004/005 просто потому, что реестр появился позже них.

| ID | Конструкция | Детектор | Статус | Подтверждено на ora2pg | Документ |
|---|---|---|---|---|---|
| GAP-001 | `PRAGMA AUTONOMOUS_TRANSACTION` — недооценка стоимости в package body | `autonomous_tx` | confirmed | 25.0 | [gap-001](gap-001-autonomous-transaction.md) |
| GAP-002 | `MERGE ... WHEN MATCHED THEN UPDATE SET ... DELETE WHERE ...` | `merge_delete_clause` | confirmed | 25.0 | [gap-002](gap-002-merge-delete-clause.md) |
| GAP-003 | `TYPE ... IS TABLE OF` / `BULK COLLECT INTO` / `FORALL` | `bulk_collect` | confirmed | 25.0 | [gap-003](gap-003-bulk-collect-forall.md) |
| GAP-004 | `COMPOUND TRIGGER` — тихий провал файлового парсера | `compound_triggers` | confirmed | 25.0 | [gap-004](gap-004-compound-trigger.md) |
| GAP-005 | `CONNECT BY` — баг подстановки `LEVEL` в `WITH RECURSIVE` | `connect_by` | confirmed | 25.0 | [gap-005](gap-005-connect-by-level.md) |
| GAP-006 | `table@dblink_name` — прямая ссылка на удалённую БД | `database_link` | confirmed | 25.0 | [gap-006](gap-006-database-link.md) |
| GAP-007 | `MODEL PARTITION BY ... DIMENSION BY ... MEASURES ... RULES` | `model_clause` | confirmed | 25.0 | [gap-007](gap-007-model-clause.md) |

Статусы: `confirmed` — воспроизведено на указанной версии ora2pg и
остаётся актуальным; `fixed-upstream` — ora2pg исправил проблему в более
новой версии (детектор в этом случае всё ещё существует, но должен быть
явно помечен устаревшим); `wont-fix` — проблема архитектурная, маловероятно
будет исправлена апстримом. Ни один статус здесь не проверяется
автоматически — это ручная пометка по факту исследования, не живой мониторинг
за релизами ora2pg. Если вы обнаружили, что более новая версия ora2pg
исправила один из этих gap'ов, откройте issue.

`dbms_utl_calls` — отдельный случай, не входит в реестр как единый GAP:
это не одна конкретная конструкция, а универсальный классификатор
конкретных вызовов `DBMS_*`/`UTL_*` (список конвертируемых — в самом
детекторе, `_CONVERTED` в `dbms_utl_calls.py`). Общий вывод по всему классу
задокументирован в `step0-show-report-baseline.md`, раздел 4.
