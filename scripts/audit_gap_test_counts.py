"""Recompute the per-GAP test counts in docs/research/AUDIT.md's summary
table, so those numbers stay a falsifiable, re-runnable claim instead of
something the reader has to trust or reverse-engineer.

A test is classified as a "guard" (false-positive-avoidance) test if its
body contains `== []` -- i.e. it asserts that on this specific input, the
detector finds nothing. This is a proxy, not a semantic analysis: it will
miss a guard test written as `assert len(findings) == 0` in an unusual
style, and it can't tell a guard test from a positive test that happens to
also contain the literal substring `== []` in an unrelated assertion or
comment. In practice, every test file in this project follows the
established `assert find_x(source) == []` convention for its guard tests
(see any tests/test_*.py for the pattern), so this proxy matches manual
inspection exactly as of the last time this script and docs/research/
AUDIT.md were updated together.

Run: python3 scripts/audit_gap_test_counts.py
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# (GAP number, detector module name, its test file(s))
GAPS = [
    ("001", "autonomous_tx", ["test_autonomous_tx.py", "test_autonomous_tx_edge_cases.py"]),
    ("002", "merge_delete_clause", ["test_merge_delete_clause.py"]),
    ("003", "bulk_collect", ["test_bulk_collect.py"]),
    ("004", "compound_triggers", ["test_compound_triggers.py"]),
    ("005", "connect_by", ["test_connect_by.py"]),
    ("006", "database_link", ["test_database_link.py"]),
    ("007", "model_clause", ["test_model_clause.py"]),
    ("008", "pivot_clause", ["test_pivot_clause.py"]),
    ("009", "object_type", ["test_object_type.py"]),
    ("010", "with_function", ["test_with_function.py"]),
    ("011", "flashback_query", ["test_flashback_query.py"]),
    ("012", "global_temp_table", ["test_global_temp_table.py"]),
    ("013", "table_partitioning", ["test_table_partitioning.py"]),
    ("014", "connect_by_nocycle", ["test_connect_by_nocycle.py"]),
    ("015", "context_object", ["test_context_object.py"]),
    ("016", "insert_all", ["test_insert_all.py"]),
    ("017", "json_table", ["test_json_table.py"]),
    ("018", "external_table", ["test_external_table.py"]),
    ("019", "sql_macro", ["test_sql_macro.py"]),
    ("020", "invisible_column", ["test_invisible_column.py"]),
    ("021", "collection_type", ["test_collection_type.py"]),
]

_TEST_DEF_RE = re.compile(r"^def (test_\w+)", re.MULTILINE)
_EMPTY_RESULT_RE = re.compile(r"==\s*\[\]|assert\s+len\([^)]*\)\s*==\s*0")


def count_tests(test_files: list[str]) -> tuple[int, int]:
    total = 0
    guards = 0
    for fname in test_files:
        text = (REPO_ROOT / "tests" / fname).read_text()
        parts = _TEST_DEF_RE.split(text)[1:]  # [name, body, name, body, ...]
        for i in range(0, len(parts), 2):
            total += 1
            if _EMPTY_RESULT_RE.search(parts[i + 1]):
                guards += 1
    return total, guards


def main() -> None:
    print(f"{'GAP':<5} {'detector':<22} {'total':>5} {'guards':>7}")
    for num, mod, files in GAPS:
        total, guards = count_tests(files)
        print(f"{num:<5} {mod:<22} {total:>5} {guards:>7}")


if __name__ == "__main__":
    main()
