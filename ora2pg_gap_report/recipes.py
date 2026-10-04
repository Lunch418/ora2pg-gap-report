"""Migration recipes: for a class of problem, the PostgreSQL pattern that
replaces the Oracle (or MySQL, or T-SQL) construct, with code that runs.

The research docs (docs/research/gap-*.md) answer "what does ora2pg get
wrong, and how do we know". A recipe answers the next question, "so what
do I write instead" -- for a class of problem, not for each detector:
CONNECT BY, CONNECT BY NOCYCLE, CONNECT_BY_ROOT and a recursive WITH
without RECURSIVE all get one page about hierarchical queries, because
the fix is one pattern.

Every ```sql block in a recipe is PostgreSQL that is loaded into a real
PostgreSQL 16 by the test suite (tests/test_recipes.py, through
--load-check), with the recipe's own DO ... ASSERT blocks checking the
pattern does what the page says. A recipe that stops working fails the
build, the same way a detector does.

The pages live in docs/recipes/, which a pip install does not ship, so
links point at GitHub; --explain prefers the local file in a checkout.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from .gap_registry import REPO_ROOT

RECIPES_DIR = REPO_ROOT / "docs" / "recipes"
_URL_BASE = "https://github.com/Lunch418/ora2pg-gap-report/blob/main/docs/recipes/"


@dataclasses.dataclass(frozen=True)
class Recipe:
    slug: str  # docs/recipes/<slug>.md and <slug>.ru.md
    title_en: str
    title_ru: str
    detectors: tuple[str, ...]

    def title(self, lang: str) -> str:
        return self.title_en if lang == "en" else self.title_ru


RECIPES: tuple[Recipe, ...] = (
    Recipe(
        "hierarchical-queries",
        "Hierarchical queries: CONNECT BY -> WITH RECURSIVE",
        "Иерархические запросы: CONNECT BY -> WITH RECURSIVE",
        ("connect_by", "connect_by_nocycle", "connect_by_pseudocolumn", "recursive_with"),
    ),
    Recipe(
        "collections-and-bulk",
        "Collections and bulk operations: arrays and set-based SQL",
        "Коллекции и массовые операции: массивы и SQL над множествами",
        ("bulk_collect", "collection_type", "table_collection", "multiset_operator"),
    ),
    Recipe(
        "autonomous-transactions",
        "Autonomous transactions",
        "Автономные транзакции",
        ("autonomous_tx",),
    ),
    Recipe(
        "package-state",
        "Package variables and application contexts",
        "Переменные пакета и контексты приложения",
        ("package_state", "context_object"),
    ),
    Recipe(
        "temporary-tables",
        "Global temporary tables",
        "Глобальные временные таблицы",
        ("global_temp_table", "mysql_temporary_table"),
    ),
    Recipe(
        "pivot-unpivot",
        "PIVOT and UNPIVOT",
        "PIVOT и UNPIVOT",
        ("pivot_clause",),
    ),
    Recipe(
        "multi-table-dml",
        "INSERT ALL, MERGE ... DELETE and upserts",
        "INSERT ALL, MERGE ... DELETE и upsert",
        (
            "insert_all",
            "merge_delete_clause",
            "mysql_on_duplicate_key_update",
            "mysql_replace_into",
            "mysql_insert_ignore",
        ),
    ),
    Recipe(
        "error-handling",
        "Errors: raising, catching and naming them",
        "Ошибки: как бросать, ловить и называть",
        ("pragma_exception_init", "mysql_signal", "mysql_declare_handler", "mssql_raiserror", "mssql_try_catch"),
    ),
    Recipe(
        "database-links",
        "Database links -> postgres_fdw",
        "Database link -> postgres_fdw",
        ("database_link",),
    ),
    Recipe(
        "builtin-packages",
        "DBMS_* and UTL_* calls",
        "Вызовы DBMS_* и UTL_*",
        ("dbms_utl_calls",),
    ),
    Recipe(
        "analytic-functions",
        "KEEP, IGNORE NULLS, WM_CONCAT and SAMPLE",
        "KEEP, IGNORE NULLS, WM_CONCAT и SAMPLE",
        ("keep_dense_rank", "ignore_nulls", "wm_concat", "sample_clause"),
    ),
    Recipe(
        "read-only-and-invisible",
        "Read-only tables and views, invisible columns and indexes",
        "Таблицы и представления только для чтения, невидимые столбцы и индексы",
        ("read_only_table", "read_only_view", "invisible_column", "invisible_index"),
    ),
    Recipe(
        "partitioning",
        "Partitioned tables",
        "Секционированные таблицы",
        ("table_partitioning",),
    ),
    Recipe(
        "tsql-expressions",
        "T-SQL expressions: TOP, IIF, DATEDIFF, SCOPE_IDENTITY, OUTPUT",
        "Выражения T-SQL: TOP, IIF, DATEDIFF, SCOPE_IDENTITY, OUTPUT",
        ("mssql_top_clause", "mssql_iif", "mssql_datediff", "mssql_scope_identity", "mssql_output_clause"),
    ),
    Recipe(
        "mysql-expressions",
        "MySQL expressions: LIMIT, LAST_INSERT_ID, DATE_FORMAT, ENUM, SET",
        "Выражения MySQL: LIMIT, LAST_INSERT_ID, DATE_FORMAT, ENUM, SET",
        (
            "mysql_limit_comma",
            "mysql_last_insert_id",
            "mysql_date_format",
            "mysql_on_update_current_timestamp",
            "mysql_enum_type",
            "mysql_set_type",
        ),
    ),
)

_BY_DETECTOR = {detector: recipe for recipe in RECIPES for detector in recipe.detectors}


def recipe_for(detector: str) -> Recipe | None:
    return _BY_DETECTOR.get(detector)


def recipe_path(recipe: Recipe, lang: str = "ru") -> Path | None:
    """The recipe's page in a source checkout, in `lang` (English at the
    base name, Russian at .ru.md), or None when docs/ isn't there."""
    path = RECIPES_DIR / (f"{recipe.slug}.ru.md" if lang == "ru" else f"{recipe.slug}.md")
    return path if path.is_file() else None


def recipe_url(recipe: Recipe, lang: str = "ru") -> str:
    return _URL_BASE + (f"{recipe.slug}.ru.md" if lang == "ru" else f"{recipe.slug}.md")
