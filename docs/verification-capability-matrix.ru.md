*[English](verification-capability-matrix.md) | Русский*

# Verification capability matrix

`--verify` (см. README, раздел "Post-migration verification") сравнивает
pre-migration находки (снапшот `--save`) с тем, что реально осталось в уже
сгенерированном `ora2pg` PostgreSQL-коде. Для части детекторов это
содержательная проверка. Для другой части — нет, и не потому что что-то
не реализовано, а потому что для них сам вопрос "осталось ли это в
выводе" тавтологичен: конструкция гарантированно не появится в выводе ни
на одной миграции, независимо от того, исправил её кто-то руками или
нет. Docstring `verification.py` объясняет это подробно; здесь — таблица
по каждому из 126 gap'ов, чтобы не листать код ради одного вопроса
"а можно ли верифицировать конкретно этот".

## Как читать колонку "режим"

- **`verbatim`** — `ora2pg` копирует помеченную Oracle-конструкцию в
  вывод практически без изменений (подтверждено для каждого детектора в
  собственном `docs/research/gap-*.md`, разделе "Вывод ora2pg"). Повторный
  прогон детектора по сгенерированному файлу — реальная проверка: если
  паттерна больше нет, кто-то осознанно переписал код руками.
  `--verify` в этом случае даёт `STILL_PRESENT` или `NOT_DETECTED`.
- **`not_verifiable`** — `ora2pg` либо полностью отбрасывает конструкцию,
  либо переписывает её в нечто другое (само ключевое слово в принципе не
  может оказаться в выводе — не потому что кто-то исправил проблему, а
  по построению), либо настолько разваливает окружающую структуру, что
  повторному обнаружению нельзя доверять. `--verify` в этом случае
  всегда выдаёт `NOT_VERIFIABLE`, а не `NOT_DETECTED` — потому что
  `NOT_DETECTED` было бы обманчивым: оно выглядело бы как "проблема
  решена", а на самом деле означало бы "мы физически не можем это
  увидеть в выводе, независимо от того, решена проблема или нет".
- **`generated_only`** — детектор (`connect_by`, GAP-005) уже анализирует
  только сгенерированный `ora2pg`-код (`--check-connect-by`); отдельной
  pre-migration находки на стороне Oracle для него нет, поэтому `--verify`
  сравнивать не с чем.

## Таблица

| GAP | Детектор | Режим | Почему |
|---|---|---|---|
| 001 | `autonomous_tx` | `not_verifiable` | Находка — про недооценку/пропуск стоимости в `SHOW_REPORT`/`--estimate_cost`, а не про форму кода. Сравнивать в сгенерированном выводе нечего. |
| 002 | `merge_delete_clause` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 003 | `bulk_collect` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 004 | `compound_triggers` | `not_verifiable` | `COMPOUND TRIGGER` полностью выпадает из файлового режима, без предупреждения. |
| 005 | `connect_by` | `generated_only` | Уже анализирует только сгенерированный код (`--check-connect-by`) — pre-migration находки для сравнения не существует. |
| 006 | `database_link` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 007 | `model_clause` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 008 | `pivot_clause` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 009 | `object_type` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 010 | `with_function` | `not_verifiable` | Окружающая структура разваливается достаточно, чтобы повторному обнаружению нельзя было доверять. |
| 011 | `flashback_query` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 012 | `global_temp_table` | `not_verifiable` | Секция `ON COMMIT` пропадает полностью, без следа. |
| 013 | `table_partitioning` | `not_verifiable` | `PARTITION BY` отбрасывается полностью. |
| 014 | `connect_by_nocycle` | `not_verifiable` | Окружающая структура разваливается достаточно, чтобы повторному обнаружению нельзя было доверять. |
| 015 | `context_object` | `not_verifiable` | Конструкция полностью пропадает из вывода, единственный след — служебная DEBUG-строка в логе. |
| 016 | `insert_all` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 017 | `json_table` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 018 | `external_table` | `not_verifiable` | Вся секция `ORGANIZATION EXTERNAL` отбрасывается. |
| 019 | `sql_macro` | `not_verifiable` | Ключевое слово `SQL_MACRO` безусловно отбрасывается. |
| 020 | `invisible_column` | `not_verifiable` | Модификатор `INVISIBLE` отбрасывается. |
| 021 | `collection_type` | `not_verifiable` | `CREATE TYPE ... TABLE OF/VARRAY OF` не появляется в выводе вовсе, только DEBUG-строка в логе. |
| 022 | `cross_apply` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 023 | `oracle_text` | `not_verifiable` | Смешанный случай: `INDEXTYPE` отбрасывается, `CONTAINS()`/аналоги копируются как есть — детектор целиком помечен `not_verifiable`, чтобы не выдавать частичный сигнал за полный. |
| 024 | `recursive_with` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 025 | `invisible_index` | `not_verifiable` | Модификатор `INVISIBLE` пропадает без следа. |
| 026 | `read_only_table` | `not_verifiable` | `READ ONLY` отбрасывается полностью. |
| 027 | `materialized_view_log` | `not_verifiable` | Конструкция полностью пропадает из вывода, единственный след — служебная DEBUG-строка в логе. |
| 028 | `identity_column` | `verbatim` | Конструкция копируется в вывод без изменений. |
| 029 | `rowid_type` | `not_verifiable` | `ROWID`/`UROWID` переписывается в `oid` — само ключевое слово никогда не сохраняется. |
| 030 | `sequence_cycle` | `not_verifiable` | Ключевое слово `CYCLE` безусловно отбрасывается. |
| 031 | `default_on_null` | `verbatim` | Клауза `ON NULL` копируется в `CREATE TABLE` без изменений. |
| 032 | `public_synonym` | `not_verifiable` | Переписывается в `CREATE VIEW`; `SYNONYM`/`FOR` никогда не сохраняются. |
| 033 | `virtual_column` | `not_verifiable` | Переписывается в обычный столбец + триггер; исходная клауза никогда не сохраняется. |
| 034 | `nested_subprogram` | `not_verifiable` | Вложенность выпрямляется; структуру нельзя повторно обнаружить. |
| 035 | `conditional_compilation` | `verbatim` | Директивы `$IF`/`$ELSIF`/`$ELSE`/`$END` копируются в тело без изменений. |
| 036 | `package_state` | `not_verifiable` | Переписывается в `set_config`/`current_setting`; исходное объявление никогда не сохраняется. |
| 037 | `index_organized_table` | `not_verifiable` | Ключевое слово `ORGANIZATION INDEX` безусловно отбрасывается. |
| 038 | `match_recognize` | `verbatim` | Вся секция MATCH_RECOGNIZE(...) копируется в вывод без изменений. |
| 039 | `connect_by_pseudocolumn` | `verbatim` | CONNECT_BY_ROOT/ISLEAF/ISCYCLE переживают конвертацию дословно, попадая в сгенерированный рекурсивный CTE. |
| 040 | `keep_dense_rank` | `verbatim` | Модификатор KEEP (DENSE_RANK ...) копируется в вывод без изменений. |
| 041 | `multiset_operator` | `verbatim` | CAST(MULTISET(...)), MULTISET UNION, MEMBER OF, SUBMULTISET OF — все копируются без изменений. |
| 042 | `sample_clause` | `verbatim` | SAMPLE (n) копируется в вывод без изменений (в TABLESAMPLE не переписывается). |
| 043 | `accessible_by` | `verbatim` | Секция копируется дословно в заголовок сгенерированной функции. |
| 044 | `local_time_zone` | `not_verifiable` | Переписывается в простой `timestamp`; слова WITH LOCAL TIME ZONE не переживают конвертацию. |
| 045 | `temporal_validity` | `not_verifiable` | Превращается в обрубок `period FOR`; именованная форма PERIOD FOR не переживает конвертацию. |
| 046 | `bitmap_index` | `not_verifiable` | Переписывается в CREATE INDEX ... USING gin; ключевое слово BITMAP не переживает конвертацию. |
| 047 | `object_table` | `not_verifiable` | `OF <тип>` становится столбцом по имени `of`; форма объектной таблицы не переживает конвертацию. |
| 048 | `ignore_nulls` | `verbatim` | IGNORE/RESPECT NULLS копируется в вывод без изменений. |
| 049 | `nlssort` | `not_verifiable` | Переписывается в оговорку COLLATE; сам вызов NLSSORT не переживает конвертацию. |
| 050 | `long_raw_type` | `not_verifiable` | Переписывается в `text`; ключевое слово LONG RAW не переживает конвертацию. |
| 051 | `anydata_type` | `verbatim` | Имя типа SYS.ANYDATA переносится в вывод без изменений. |
| 052 | `system_trigger` | `verbatim` | Область ON DATABASE/SCHEMA переживает конвертацию (в нижнем регистре) в сгенерированном CREATE TRIGGER. |
| 053 | `trigger_follows` | `not_verifiable` | Оговорка переживает конвертацию, но попадает в тело *функции* триггера, а не в заголовок CREATE TRIGGER, который читает этот детектор — дословно в файле и при этом не находится повторно. |
| 054 | `table_collection` | `verbatim` | Оператор TABLE(...) копируется в вывод без изменений. |
| 055 | `cursor_expression` | `verbatim` | CURSOR(SELECT ...) копируется в вывод без изменений. |
| 056 | `for_update_wait` | `verbatim` | Оговорка WAIT n копируется в вывод без изменений. |
| 057 | `rownum_dml` | `not_verifiable` | Переписывается в LIMIT n; ключевое слово ROWNUM не переживает конвертацию. |
| 058 | `to_date_rr` | `verbatim` | Формат RR остаётся на месте внутри TO_DATE. |
| 059 | `authid_clause` | `not_verifiable` | Процедура выбрасывается целиком, поэтому в выводе не остаётся вообще ничего, что можно было бы найти повторно. |
| 060 | `pragma_exception_init` | `not_verifiable` | Сам PRAGMA выброшен; в обработчике остаётся только подставленный SQLSTATE. |
| 061 | `subtype_range` | `not_verifiable` | Становится CREATE DOMAIN; ключевое слово SUBTYPE не переживает конвертацию. |
| 062 | `alt_quote_literal` | `verbatim` | Литерал q'...' копируется в вывод без изменений. |
| 063 | `goto_statement` | `verbatim` | GOTO и метка копируются в вывод без изменений. |
| 064 | `cursor_rowtype` | `not_verifiable` | %ROWTYPE переживает конвертацию, но `CURSOR c IS` становится `c CURSOR FOR`, и имя курсора для этого детектора больше не разрешается. |
| 065 | `wm_concat` | `verbatim` | Вызов WM_CONCAT копируется в вывод без изменений (в отличие от LISTAGG). |
| 066 | `read_only_view` | `not_verifiable` | Оговорка WITH READ ONLY выбрасывается безусловно. |
| 067 | `sdo_geometry` | `not_verifiable` | Переписывается в тип PostGIS `geometry`; имя SDO_GEOMETRY не переживает конвертацию. |

### Oracle (GAP-112..124)

| # | Детектор | Режим | Почему |
|---|---|---|---|
| 112 | `table_if_not_exists` | `not_verifiable` | Превращается в `CREATE TABLE if (`, IF NOT EXISTS в выводе нет. |
| 113 | `identity_on_null` | `not_verifiable` | Переписывается в BY DEFAULT AS IDENTITY; ON NULL не переживает конвертацию. |
| 114 | `package_constant_chain` | `not_verifiable` | Объявления нет; остаются только склеенные вызовы current_setting(). |
| 115 | `ref_cursor_type` | `not_verifiable` | Становится CREATE TYPE ... AS REFCURSOR; TYPE ... IS REF CURSOR не переживает конвертацию. |
| 116 | `repeated_package_call` | `not_verifiable` | Вызов получает скобки; форма без скобок не переживает конвертацию. |
| 117 | `trigger_package_call` | `verbatim` | Вызов копируется в функцию триггера без изменений. |
| 118 | `statement_trigger` | `not_verifiable` | Заголовок уровня команды заменяется на FOR EACH ROW. |
| 119 | `package_constant_default` | `not_verifiable` | Умолчание остаётся, но вне пакета, который читает детектор. |
| 120 | `package_type_anchor` | `not_verifiable` | RECORD/SUBTYPE становится CREATE TYPE/DOMAIN; --load-check узнаёт скопированную привязку. |
| 121 | `package_type_reference` | `not_verifiable` | Объявление становится CREATE TYPE/DOMAIN; остаётся только использование без схемы. |
| 122 | `supplied_package_call` | `verbatim` | Вызов копируется без изменений. |
| 123 | `dbms_sleep` | `not_verifiable` | DBMS_LOCK.SLEEP становится голым pg_sleep, его чинит --fix. |
| 124 | `schema_qualified_name` | `verbatim` | Схема остаётся у таблиц, представлений, последовательностей; пропадает, когда файл создаёт схему. |

### MySQL/MariaDB (`ora2pg -m`)

| # | Детектор | Режим | Почему |
|---|---|---|---|
| 068 | `mysql_enum_type` | `not_verifiable` | Переписывается в ссылку на синтезированный тип <таблица>_<столбец>_t; сам ENUM(...) не переживает конвертацию. |
| 069 | `mysql_on_update_current_timestamp` | `verbatim` | ON UPDATE CURRENT_TIMESTAMP копируется прямо в сгенерированный DEFAULT. |
| 070 | `mysql_on_duplicate_key_update` | `verbatim` | Всё предложение ON DUPLICATE KEY UPDATE копируется в тело функции без изменений. |
| 071 | `mysql_signal` | `verbatim` | SIGNAL/RESIGNAL копируются без изменений (теряется только SET перед MESSAGE_TEXT). |
| 072 | `mysql_fulltext_index` | `verbatim` | 'FULLTEXT KEY'/'FULLTEXT INDEX' остаётся в выводе — в другом регистре, но с ключевыми словами. |
| 073 | `mysql_key_index` | `verbatim` | В выводе остаётся заглушка 'key <ИМЯ>' там, где ожидался столбец. |
| 074 | `mysql_spatial_index` | `verbatim` | Та же форма, что у FULLTEXT: 'spatial KEY' остаётся в списке столбцов. |
| 075 | `mysql_limit_comma` | `verbatim` | `LIMIT n, m` копируется прямо в тело функции. |
| 076 | `mysql_replace_into` | `verbatim` | REPLACE INTO копируется в тело функции без изменений. |
| 077 | `mysql_insert_ignore` | `verbatim` | INSERT IGNORE копируется в тело функции без изменений. |
| 078 | `mysql_prepare_from` | `verbatim` | `PREPARE <имя> FROM` копируется без изменений (только @переменная становится обычной). |
| 079 | `mysql_last_insert_id` | `verbatim` | Вызов LAST_INSERT_ID() копируется без изменений. |
| 080 | `mysql_auto_increment_start` | `not_verifiable` | Опция таблицы выбрасывается; AUTO_INCREMENT=<n> в вывод не попадает по построению. |
| 081 | `mysql_date_format` | `not_verifiable` | Переписывается в конструктор строки; имя DATE_FORMAT не переживает конвертацию. |
| 082 | `mysql_foreign_key` | `not_verifiable` | Выбрасывается целиком — ни одного FOREIGN KEY в выводе. |
| 083 | `mysql_zero_date` | `not_verifiable` | Молча переписывается в '1970-01-01'; литерал нулевой даты не переживает конвертацию. |
| 084 | `mysql_declare_handler` | `not_verifiable` | Выбрасывается целиком, на его месте пустые строки. |
| 085 | `mysql_collate` | `not_verifiable` | Предложение COLLATE/CHARACTER SET выбрасывается из определения столбца. |
| 086 | `mysql_set_type` | `not_verifiable` | Переписывается в обычный `text`; запись SET(...) не переживает конвертацию. |
| 106 | `mysql_delimiter_routine` | `not_verifiable` | Директива DELIMITER попадает в тело лишь как посторонняя строка. |
| 107 | `mysql_delimiter_trigger` | `not_verifiable` | Триггер не генерируется вовсе. |
| 108 | `mysql_definer_procedure` | `not_verifiable` | Процедура не генерируется вовсе в -t PROCEDURE. |
| 109 | `mysql_versioned_comment` | `not_verifiable` | Объект удаляется вместе с комментариями. |
| 110 | `mysql_create_table_if_not_exists` | `not_verifiable` | Превращается в `CREATE TABLE if (`, IF NOT EXISTS в выводе нет. |
| 111 | `mysql_temporary_table` | `not_verifiable` | TEMPORARY выбрасывается, остаётся обычный CREATE TABLE. |

### MSSQL / T-SQL (`ora2pg -M`)

| # | Детектор | Режим | Почему |
|---|---|---|---|
| 087 | `mssql_bracket_identifier` | `verbatim` | Скобки остаются в сгенерированном идентификаторе — в этом и состоит проблема. |
| 088 | `mssql_newid_default` | `not_verifiable` | Переписывается в uuid_generate_v4(); запись NEWID() не переживает конвертацию. |
| 089 | `mssql_update_set` | `not_verifiable` | Ключевое слово SET удаляется при конвертации, исходной формы больше нет. |
| 090 | `mssql_identity_column` | `not_verifiable` | IDENTITY выбрасывается целиком; в вывод ничего не попадает. |
| 091 | `mssql_parameterless_procedure` | `not_verifiable` | Находка — про сгенерированный блок DECLARE, а не про сохранившийся фрагмент исходника. |
| 092 | `mssql_if_statement` | `verbatim` | IF сохраняется (неверно закрытый или без THEN), так что повторное обнаружение осмысленно. |
| 093 | `mssql_raiserror` | `verbatim` | RAISERROR/THROW копируются без изменений. |
| 094 | `mssql_try_catch` | `verbatim` | Вся конструкция TRY/CATCH копируется без изменений. |
| 095 | `mssql_top_clause` | `verbatim` | TOP n копируется без изменений. |
| 096 | `mssql_scope_identity` | `verbatim` | Вызов копируется без изменений. |
| 097 | `mssql_output_clause` | `verbatim` | Предложение OUTPUT копируется без изменений. |
| 098 | `mssql_iif` | `verbatim` | Вызов IIF копируется без изменений. |
| 099 | `mssql_datediff` | `verbatim` | Вызов DATEDIFF копируется без изменений. |
| 100 | `mssql_charindex` | `not_verifiable` | Переписывается в position(); имя CHARINDEX не переживает конвертацию. |
| 101 | `mssql_filtered_index` | `not_verifiable` | Вся инструкция CREATE INDEX выбрасывается. |
| 102 | `mssql_foreign_key` | `not_verifiable` | Выбрасывается целиком — ни одного FOREIGN KEY в выводе. |
| 103 | `mssql_collation` | `not_verifiable` | Предложение COLLATE выбрасывается, столбец становится citext. |
| 104 | `mssql_computed_column` | `not_verifiable` | Переписывается в триггер; синтаксис столбца `AS (выражение)` не переживает конвертацию. |
| 105 | `mssql_rowversion` | `not_verifiable` | Переписывается в bytea; имя ROWVERSION не переживает конвертацию. |
| 125 | `mssql_schema_qualified_name` | `verbatim` | Схема остаётся у всех имён; пропадает, когда файл её создаёт (это делает `--fix`). |
| 126 | `mssql_go_separator` | `verbatim` | GO остаётся - внутри тела подпрограммы. |

Итого среди самих 126 gap'ов: 55 `verbatim`, 70 `not_verifiable`
(включая `autonomous_tx`, но по другой причине — см. выше), 1
`generated_only` (`connect_by`).

Отдельно от реестра gap'ов, но тоже в `VERIFICATION_MODE`: `dbms_utl_calls`
— это классификатор конкретных вызовов `DBMS_*`/`UTL_*`, а не отдельный
зарегистрированный gap (у него нет номера GAP-NNN), поэтому в таблице выше
его нет. Режим — `verbatim`: классифицируемые вызовы копируются в вывод
без изменений.

Эта таблица и `ora2pg_gap_report/verification.py::VERIFICATION_MODE` — один
источник правды: `scripts/doctor.py` проверяет, что режим задан для
каждого детектора из реестра, но не то, что эта таблица не разошлась с
кодом построчно (текстовое markdown-описание причины не поддаётся
автоматической сверке). При добавлении нового детектора см.
`CONTRIBUTING.md`/`DEVELOPMENT.md` — режим верификации задаётся в паре с
самим детектором, эту таблицу нужно обновлять вручную.
