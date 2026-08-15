from ora2pg_gap_report.detectors.oracle_text import find_oracle_text_usage


def test_context_domain_index_is_flagged():
    source = (
        "create table articles (article_id number, body clob);\n"
        "create index articles_body_idx on articles(body)\n"
        "indextype is ctxsys.context;\n"
    )
    findings = find_oracle_text_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "ARTICLES_BODY_IDX"
    assert findings[0].snippet == "INDEXTYPE IS CTXSYS.CONTEXT"
    assert findings[0].severity == "high"


def test_ctxcat_and_ctxrule_variants_are_also_flagged():
    ctxcat = "create index idx1 on t(c) indextype is ctxsys.ctxcat;\n"
    ctxrule = "create index idx2 on t(c) indextype is ctxsys.ctxrule;\n"
    assert len(find_oracle_text_usage(ctxcat)) == 1
    assert len(find_oracle_text_usage(ctxrule)) == 1


def test_contains_call_is_flagged_and_attributed():
    source = (
        "create or replace package body search_pkg as\n"
        "  procedure find_articles is\n"
        "    v_count number;\n"
        "  begin\n"
        "    select count(*) into v_count from articles\n"
        "    where contains(body, 'oracle') > 0;\n"
        "  end find_articles;\n"
        "end search_pkg;\n"
        "/\n"
    )
    findings = find_oracle_text_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SEARCH_PKG.FIND_ARTICLES"
    assert findings[0].snippet == "CONTAINS(...)"


def test_catsearch_and_matches_are_also_flagged():
    source = (
        "create or replace procedure noop as\n"
        "begin\n"
        "  select 1 from t where catsearch(c, 'x', null) > 0;\n"
        "  select 1 from t where matches(c, 'x') > 0;\n"
        "end;\n"
        "/\n"
    )
    findings = find_oracle_text_usage(source)
    assert {f.snippet for f in findings} == {"CATSEARCH(...)", "MATCHES(...)"}


def test_ordinary_index_is_not_flagged():
    source = "create index idx1 on t(c);\n"
    assert find_oracle_text_usage(source) == []


def test_string_and_comment_content_does_not_trigger_a_false_positive():
    source = (
        "-- see contains() and indextype is ctxsys.context in the docs\n"
        "create or replace procedure noop as\n"
        "  v_msg varchar2(100) := 'contains and indextype is ctxsys.context';\n"
        "begin\n"
        "  null;\n"
        "end;\n"
        "/\n"
    )
    assert find_oracle_text_usage(source) == []


def test_real_oracle_sample_schema_index_is_flagged():
    # The exact real-world shape this gap was found on: sup_text_idx from
    # Oracle's own official sample schemas (oracle-samples/db-sample-schemas,
    # sales_history/sh_populate.sql), verbatim -- not a synthetic
    # construction. Also confirms the detector still matches with a
    # PARAMETERS(...) clause after INDEXTYPE, which this real index has.
    source = "CREATE INDEX sup_text_idx ON supplementary_demographics(comments)\n   INDEXTYPE IS ctxsys.context PARAMETERS('nopopulate');\n"
    findings = find_oracle_text_usage(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SUP_TEXT_IDX"


def test_user_defined_function_of_the_same_name_is_not_flagged():
    # 'contains'/'matches' are entirely plausible names for an unrelated
    # user-defined function (e.g. a collection-membership helper) -- a
    # call not immediately compared against a number/bind variable isn't
    # real Oracle Text usage.
    source = (
        "create or replace package body util_pkg as\n"
        "  function contains(p_list varchar2, p_val varchar2) return boolean is\n"
        "  begin\n"
        "    return instr(p_list, p_val) > 0;\n"
        "  end contains;\n"
        "\n"
        "  procedure noop is\n"
        "    v_result boolean;\n"
        "  begin\n"
        "    v_result := contains('a,b,c', 'b');\n"
        "  end noop;\n"
        "end util_pkg;\n"
        "/\n"
    )
    assert find_oracle_text_usage(source) == []


def test_contains_without_a_trailing_numeric_comparison_is_not_flagged():
    source = "select contains(body, 'x') from articles;\n"
    assert find_oracle_text_usage(source) == []


def test_contains_with_bind_variable_comparison_is_flagged():
    source = "select 1 from articles where contains(body, 'x') > :min_score;\n"
    findings = find_oracle_text_usage(source)
    assert len(findings) == 1
