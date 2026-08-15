from ora2pg_gap_report.detectors.context_object import find_context_declarations


def test_create_context_is_flagged():
    source = "create context hr_ctx using hr.set_ctx_pkg;\n"
    findings = find_context_declarations(source)
    assert len(findings) == 1
    assert findings[0].object_name == "HR_CTX"
    assert findings[0].severity == "medium"


def test_create_or_replace_context_is_flagged():
    source = "create or replace context hr_ctx using hr.set_ctx_pkg;\n"
    findings = find_context_declarations(source)
    assert len(findings) == 1
    assert findings[0].object_name == "HR_CTX"


def test_ordinary_table_is_not_flagged():
    source = "create table orders (order_id number);\n"
    assert find_context_declarations(source) == []
