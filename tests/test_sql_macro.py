from ora2pg_gap_report.detectors.sql_macro import find_sql_macros


def test_standalone_sql_macro_function_is_flagged():
    source = (
        "create or replace function in_top_region(p_region varchar2) return varchar2 sql_macro is\n"
        "begin\n"
        "  return 'region in (''EU'', ''US'')';\n"
        "end;\n"
        "/\n"
    )
    findings = find_sql_macros(source)
    assert len(findings) == 1
    assert findings[0].object_name == "IN_TOP_REGION"
    assert findings[0].severity == "high"


def test_sql_macro_nested_in_package_is_attributed_to_the_function():
    source = (
        "create or replace package body region_pkg as\n"
        "  function in_top_region(p_region varchar2) return varchar2 sql_macro is\n"
        "  begin\n"
        "    return 'region in (''EU'')';\n"
        "  end;\n"
        "end region_pkg;\n"
        "/\n"
    )
    findings = find_sql_macros(source)
    assert len(findings) == 1
    assert findings[0].object_name == "REGION_PKG.IN_TOP_REGION"


def test_ordinary_function_is_not_flagged():
    source = (
        "create or replace function add_two(a number, b number) return number is\n"
        "begin\n"
        "  return a + b;\n"
        "end;\n"
        "/\n"
    )
    assert find_sql_macros(source) == []
