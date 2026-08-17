from ora2pg_gap_report.detectors.public_synonym import find_public_synonyms


def test_public_synonym_is_flagged():
    source = "create public synonym employees for hr.employees;\n"
    findings = find_public_synonyms(source)
    assert len(findings) == 1
    assert findings[0].object_name == "EMPLOYEES"
    assert findings[0].severity == "high"
    assert "EMPLOYEES" in findings[0].snippet.upper()


def test_private_synonym_without_public_is_also_flagged():
    source = "create synonym employees for hr.employees;\n"
    findings = find_public_synonyms(source)
    assert len(findings) == 1


def test_synonym_for_a_different_base_name_is_still_flagged():
    source = "create public synonym employees for hr.emp_table;\n"
    findings = find_public_synonyms(source)
    assert len(findings) == 1
    assert findings[0].snippet == "FOR EMP_TABLE"


def test_synonym_without_schema_prefix_on_target_is_flagged():
    source = "create public synonym employees for employees_base;\n"
    findings = find_public_synonyms(source)
    assert len(findings) == 1


def test_ordinary_table_is_not_flagged():
    source = "create table employees (emp_id number);\n"
    assert find_public_synonyms(source) == []


def test_synonym_is_not_misattributed_to_a_later_unrelated_synonym():
    source = (
        "create public synonym orders for sales.orders;\n"
        "create public synonym invoices for billing.invoices;\n"
    )
    findings = find_public_synonyms(source)
    assert len(findings) == 2
    assert findings[0].object_name == "ORDERS"
    assert findings[1].object_name == "INVOICES"


def test_unterminated_statement_does_not_bleed_into_an_earlier_synonym():
    source = (
        "create public synonym small_lookup for hr.small_lookup\n"
        "create public synonym employees for hr.employees\n"
    )
    findings = find_public_synonyms(source)
    assert len(findings) == 2


def test_reported_line_is_the_synonym_statement_line():
    source = (
        "-- comment\n"
        "create public synonym employees\n"
        "  for hr.employees;\n"
    )
    findings = find_public_synonyms(source)
    assert len(findings) == 1
    assert findings[0].line == 2
