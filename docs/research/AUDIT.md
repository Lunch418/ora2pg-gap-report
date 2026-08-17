# Аудит реестра: доказательная база по каждому из подтверждённых gap'ов

Этот документ — не новое исследование, а проверка того, что уже
задокументировано в [`GAP_REGISTRY.md`](GAP_REGISTRY.md): для каждого
подтверждённого gap'а здесь сведено воедино, что конкретно доказывает
его существование и что доказывает отсутствие ложных срабатываний у
соответствующего детектора.

Критерии проверки (по одному разу для каждого GAP-NNN):

1. **Research-документ** — существует, содержит минимальный
   воспроизводимый пример.
2. **Реальный вывод ora2pg** — не гипотеза "наверное не сработает", а
   буквальный вывод `ora2pg -t ... -o ...` на этом примере.
3. **Expected vs Actual** — что должно было получиться в PostgreSQL и что
   получилось на самом деле; для большинства gap'ов это буквальная ошибка
   реального PostgreSQL 16 при загрузке/вызове сгенерированного кода.
4. **Детектор** — файл в `ora2pg_gap_report/detectors/`, с присвоенным
   severity.
5. **Регрессионные тесты** — количество тестов и сколько из них —
   guard-тесты на ложное срабатывание (посчитано программно: тест
   классифицируется как guard, если содержит `== []` — «на этом входе
   находок быть не должно» — а не просто по названию функции).

Числа тестов в этом документе получены прогоном скрипта по актуальному
дереву тестов, а не подсчитаны вручную — см. «Как перепроверить» внизу.

## Сводная таблица

| GAP | Детектор | Sev | Doc §§ полны | ora2pg output | PG error/поведение | Тесты (всего/guard) | Проверено на реальном открытом коде |
|---|---|---|---|---|---|---|---|
| 001 | `autonomous_tx` | high | ✅ | ✅ (`logger.pkb`, dblink-обёртка) | н/д — это баг оценки стоимости, не синтаксиса | 16 / 3 (`test_autonomous_tx.py` + `test_autonomous_tx_edge_cases.py`) | да — `test_real_open_source_utplsql_test_helper_is_attributed` встраивает реальный фрагмент `main_helper.pkb`, `test_real_open_source_utplsql_hidden_pragma_inside_dynamic_sql_is_found` — скрытую в динамическом SQL `PRAGMA` из `run_helper.pkb`, оба из `utPLSQL` |
| 002 | `merge_delete_clause` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "WHERE"` | 5 / 3 | нет |
| 003 | `bulk_collect` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "IS"` | 12 / 5 | да — `test_local_collection_type_in_a_package_spec_is_attributed_not_unknown` (`amazon_aws_s3_pkg.pks`, `alexandria-plsql-utils`), `test_real_open_source_utplsql_bulk_collect_into_is_attributed` (`main_helper.pkb`, `utPLSQL`) и `test_real_open_source_utplsql_bulk_collect_hidden_inside_dynamic_sql_is_found` — скрытый в динамическом SQL `BULK COLLECT INTO` из `coverage_helper.pkb` (`utPLSQL`) |
| 004 | `compound_triggers` | high | ✅ | ✅ (`-- Nothing found of type TRIGGER`) | н/д — триггер целиком выпадает из вывода ora2pg | 5 / 3 | нет |
| 005 | `connect_by` | high | ✅ | ✅ (сгенерированный `WITH RECURSIVE`) | ✅ `c.level` не существует в CTE | 11 / 3 | нет (детектор анализирует вывод ora2pg, не исходный код — не применимо к сканированию исходников напрямую) |
| 006 | `database_link` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "@"` | 5 / 3 | нет |
| 007 | `model_clause` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "PARTITION"` | 5 / 3 | нет |
| 008 | `pivot_clause` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "("` | 6 / 2 | нет |
| 009 | `object_type` | high | ✅ | ✅ (`--estimate_cost` вернул 0 строк) | н/д — пробел в оценке стоимости, не в синтаксисе | 7 / 2 | да — `test_real_open_source_object_type_is_flagged` (`t_soap_envelope.pks`, `alexandria-plsql-utils`) и `test_real_open_source_utplsql_object_types_are_flagged` (`demo_equal_matcher.sql`, `utPLSQL`) |
| 010 | `with_function` | high | ✅ | ✅ | ✅ `ERROR: syntax error at end of input` (структура блока разрушена) | 4 / 1 | да — `test_real_open_source_excelgen_with_function_is_flagged` встраивает реальный `WITH FUNCTION get_xlsx(...)` из тестового набора `mbleron/ExcelGen` |
| 011 | `flashback_query` | high | ✅ | ✅ (искажённый `statement_timestamp()`) | ✅ `ERROR: syntax error at or near "timestamp"` | 4 / 1 | нет |
| 012 | `global_temp_table` | high | ✅ | ✅ | ✅ строка пережила `COMMIT` вопреки Oracle-семантике | 6 / 2 | да — `test_real_open_source_utplsql_global_temp_table_is_flagged` встраивает реальную таблицу `ut_compound_data_diff_tmp` из `utPLSQL` |
| 013 | `table_partitioning` | high | ✅ | ✅ | н/д — секции молча пропадают, не ошибка | 10 / 4 | да — `test_real_oracle_sample_schema_sales_table_is_flagged` встраивает реальную таблицу `SALES` из официальной Oracle SH-схемы (`db-sample-schemas`) |
| 014 | `connect_by_nocycle` | high | ✅ | ✅ (`WITH RECURSIVE` до `DECLARE`) | ✅ `ERROR` на этапе компиляции тела | 4 / 1 | нет |
| 015 | `context_object` | medium | ✅ | ✅ (только DEBUG-строка в логе) | н/д — конструкция пропадает без следа | 3 / 1 | нет |
| 016 | `insert_all` | high | ✅ | ✅ | ✅ `ERROR: "big_orders" is not a known variable` | 5 / 2 | нет |
| 017 | `json_table` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "COLUMNS"` | 5 / 3 | да — `test_json_table_inside_a_view_is_attributed_not_unknown` (в `tests/test_cli.py`) встраивает реальный `product_reviews` view из `db-sample-schemas` |
| 018 | `external_table` | high | ✅ | ✅ | н/д — секция пропадает, таблица создаётся пустой | 4 / 1 | нет |
| 019 | `sql_macro` | high | ✅ | ✅ | ✅ `ERROR: argument of WHERE must be type boolean` | 3 / 1 | нет |
| 020 | `invisible_column` | high | ✅ | ✅ | ✅ столбец появился в `SELECT *` вопреки Oracle-семантике | 8 / 2 | нет |
| 021 | `collection_type` | high | ✅ | ✅ (`[DEBUG] unhandled line`) | ✅ `ERROR: type "phone_list_t" does not exist` | 8 / 3 | да — `test_real_open_source_utplsql_collection_type_is_flagged` встраивает реальный тип `demo_departments` из `utPLSQL` |
| 022 | `cross_apply` | high | ✅ | ✅ | ✅ `ERROR: syntax error at or near "APPLY"` | 3 / 1 | нет |
| 023 | `oracle_text` | high | ✅ | ✅ | ✅ `ERROR: function contains(text, unknown) does not exist` | 12 / 4 | да — `test_real_oracle_sample_schema_index_is_flagged` встраивает реальный индекс `sup_text_idx` из официальной Oracle SH-схемы (`db-sample-schemas`) |
| 024 | `recursive_with` | high | ✅ | ✅ | ✅ `ERROR: relation "tree" does not exist` (нужен `WITH RECURSIVE`) | 8 / 5 | нет |
| 025 | `invisible_index` | medium | ✅ | ✅ | н/д — оптимизатор молча начинает учитывать индекс | 8 / 3 | нет |
| 026 | `read_only_table` | high | ✅ | ✅ | ✅ INSERT прошёл там, где Oracle гарантированно блокирует его (ORA-12081) | 7 / 3 | нет |
| 027 | `materialized_view_log` | high | ✅ | ✅ (`[DEBUG] unhandled line`) | н/д — журнал пропадает без следа | 3 / 2 | нет |
| 028 | `identity_column` | high | ✅ | ✅ (лишняя пара скобок в выводе) | ✅ `ERROR: syntax error at or near "("` | 5 / 2 | нет |
| 029 | `rowid_type` | high | ✅ | ✅ (`ROWID`/`UROWID` → `oid`) | ✅ `ERROR: invalid input syntax for type oid` при INSERT реального значения | 11 / 4 | нет |
| 030 | `sequence_cycle` | high | ✅ | ✅ (секция `CYCLE` пропадает) | ✅ `ERROR: nextval: reached maximum value of sequence` после исчерпания диапазона | 6 / 2 | нет |
| 031 | `default_on_null` | high | ✅ | ✅ (`ON NULL` копируется как есть) | ✅ `ERROR: syntax error at or near "ON"` уже на CREATE TABLE | 7 / 2 | нет |
| 032 | `public_synonym` | high | ✅ | ✅ (переписан в `CREATE VIEW` без схемы) | ✅ `ERROR: relation ... does not exist` при совпадении имён | 8 / 1 | нет |
| 033 | `virtual_column` | medium | ✅ | ✅ (переписан в столбец + триггер) | н/д — значение корректно, теряется только защита от явного присваивания | 8 / 4 | нет |

**33/33 по каждому из первых пяти критериев.** Отдельная колонка —
проверка на реальном открытом коде: 9 детекторов (`autonomous_tx`,
`bulk_collect`, `object_type`, `global_temp_table`, `table_partitioning`,
`json_table`, `collection_type`, `oracle_text`, `with_function`) реально
сработали при сканировании 247 298 строк открытого кода (точный свежий
подсчёт по всем семи репозиториям вместе на момент этой проверки, каждый
— свежий `git clone --depth 1`, не сумма отдельных, ранее запомненных
чисел по каждому репозиторию) из семи независимых проектов —
`mortenbra/alexandria-plsql-utils`, `oracle-samples/db-sample-schemas`,
`utPLSQL/utPLSQL` (фреймворк юнит-тестирования PL/SQL),
`OraOpenSource/Logger`, `method5/plsql_lexer` (лексер/токенизатор
PL/SQL — с нестандартными расширениями файлов `.plsql`/`.bdy`/`.spc`,
переданными явно, не через рекурсивный обход директории по
расширениям), `mbleron/ExcelGen` (генератор Excel-файлов) и
`osalvador/tePLSQL` (шаблонизатор с активным использованием
`EXECUTE IMMEDIATE`) — и для каждого из этих девяти в дереве тестов
лежит постоянный регрессионный тест, встраивающий реальный фрагмент того
самого исходника (не гипотетический пример), так что находка остаётся
проверяемой в любой момент, а не только "было замечено в сессии
однажды". Расширение корпуса с четырёх проектов до семи не выявило ни
одного некорректного срабатывания и ни одного падения — включая два
файла (`ExcelGen.pkb`, `plsql_parser.bdy`), где `EXECUTE IMMEDIATE`
реально строит код динамически (вплоть до создания временной функции с
шаблонной подстановкой имени схемы), ни разу не спровоцировав ложную
атрибуцию: ни один из этих динамически создаваемых объектов не попал в
индекс контейнеров как настоящий (в этих двух конкретных случаях внутри
динамического кода не оказалось самой конструкции ни одного детектора —
подтверждает отсутствие падений/порчи данных, не добавляет новую
находку). Из более раннего расширения (два проекта → четыре) осталась
уже задокументированная честная граница применимости —
`object_name='UNKNOWN'` на анонимном `declare...begin...end;`-блоке без
имени (install-скрипт, не выгрузка `DBMS_METADATA.GET_DDL`), закреплено
тестом
`test_real_open_source_logger_install_script_anonymous_block_is_unknown_not_a_crash`
в `tests/test_bulk_collect.py`.

Отдельно от расширения корпуса: 14 детекторов, использующих общий индекс
атрибуции (`bulk_collect`, `connect_by_nocycle`, `cross_apply`,
`database_link`, `flashback_query`, `insert_all`, `json_table`,
`merge_delete_clause`, `model_clause`, `oracle_text`, `pivot_clause`,
`recursive_with`, `sql_macro`, `with_function`), и отдельно
`autonomous_tx` теперь видят целевую конструкцию, даже если она построена
динамически внутри `EXECUTE IMMEDIATE` — на этом же корпусе нашлись и
подтвердились ровно два новых реальных случая: скрытая `PRAGMA
AUTONOMOUS_TRANSACTION` и скрытый `BULK COLLECT INTO`, оба в `utPLSQL`,
оба верно приписаны реальной процедуре в статическом дереве исходников
(не вымышленному объекту, существующему только в момент выполнения) —
см. раздел «Конструкции, спрятанные в динамическом SQL» в
`docs/ARCHITECTURE.md` для дизайна и
`tests/test_plsql_lex.py`/`tests/test_autonomous_tx.py`/
`tests/test_bulk_collect.py` для регрессионных тестов на настоящих
фрагментах.

Остальные детекторы не встретили свою целевую конструкцию ни в одном из
этих семи корпусов — ожидаемо: часть этих конструкций (`SQL_MACRO`,
`CREATE CONTEXT`, `INVISIBLE`-столбцы и -индексы, `ORGANIZATION
EXTERNAL`, `CONNECT BY NOCYCLE`, `CROSS APPLY`, нативная рекурсивная
`WITH` без `RECURSIVE`, `READ ONLY`-таблицы, `MATERIALIZED VIEW LOG`,
`IDENTITY` с опциями) — редкие, специфичные фичи Oracle, которые
статистически маловероятно встретить даже в семи открытых проектах.
Для них "доказательство отсутствия ложных срабатываний" — это
целенаправленные unit-тесты на известные коллизионные сценарии
(партиционированный outer join, оконные функции, GRANT-списки,
комментарии/строки, вложенные
локальные объявления и т.д.), а не статистика по большому корпусу.

## Что именно значит «Doc §§ полны» для GAP-001/004/005

Эти три документа используют другую структуру заголовков (`## Что здесь
на самом деле не так` вместо отдельных `## Минимальный пример` / `##
Вывод ora2pg`) — они написаны раньше, до того как сложился текущий
шаблон. Содержательно там есть всё то же самое (минимальный пример,
реальный вывод ora2pg, `Reproducible: YES`, версия ora2pg, вердикт) —
проверено построчным чтением при подготовке этого аудита, не
автоматической проверкой по названиям заголовков.

## Как перепроверить это самостоятельно

```sh
pytest -v                                    # см. точное число ниже
ruff check ora2pg_gap_report/ tests/          # без замечаний
python3 scripts/audit_gap_test_counts.py      # пересчитать колонку "Тесты (всего/guard)" таблицы выше
```

На момент последнего обновления этого документа: **387 тестов** (386
проходят, 1 намеренно пропущен — требует установленный `ora2pg`,
см. `--check-connect-by`). Колонка "Тесты (всего/guard)" в таблице выше —
не ручной подсчёт, а буквальный вывод `scripts/audit_gap_test_counts.py`
на момент последнего обновления этого файла; при добавлении новых тестов
достаточно перезапустить скрипт и обновить таблицу его выводом.

Живая перепроверка конкретного gap'а на реальном PostgreSQL — по шагам
конкретного `docs/research/gap-NNN-*.md`: команда `ora2pg`, вывод, затем
`psql -f` и `CALL`/`SELECT`, с точно теми же результатами, что
задокументированы (`ora2pg` 25.0 и PostgreSQL 16 использовались во всех
случаях в этом реестре).
