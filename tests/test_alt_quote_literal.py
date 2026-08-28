from ora2pg_gap_report.detectors.alt_quote_literal import find_alt_quote_literals


def test_a_bracket_delimited_q_literal_is_flagged():
    source = (
        "CREATE OR REPLACE PROCEDURE say IS\n"
        "  msg VARCHAR2(100) := q'[it's a test]';\n"
        "BEGIN\n"
        "  DBMS_OUTPUT.PUT_LINE(msg);\n"
        "END;\n"
    )
    findings = find_alt_quote_literals(source)
    assert len(findings) == 1
    assert findings[0].object_name == "SAY"
    assert findings[0].snippet == "q'[..."
    assert findings[0].severity == "high"
    assert findings[0].line == 2


def test_other_delimiters_are_matched():
    for text in ["q'{a}'", "q'(a)'", "q'<a>'", "q'!a!'", "q'#a#'"]:
        assert len(find_alt_quote_literals(f"x := {text};\n")) == 1, text


def test_the_national_character_spelling_is_matched():
    assert len(find_alt_quote_literals("x := nq'[hi]';\n")) == 1


def test_uppercase_q_is_matched():
    assert len(find_alt_quote_literals("x := Q'[hi]';\n")) == 1


def test_an_ordinary_string_literal_is_not_flagged():
    assert find_alt_quote_literals("x := 'it''s a test';\n") == []


def test_a_q_literal_inside_a_comment_is_not_flagged():
    # The whole reason this detector runs on mask_comments_only() rather
    # than on the raw source.
    assert find_alt_quote_literals("-- x := q'[old value]';\nSELECT 1 FROM dual;\n") == []


def test_a_block_comment_containing_a_q_literal_is_not_flagged():
    assert find_alt_quote_literals("/* q'[note]' */\nSELECT 1 FROM dual;\n") == []


def test_an_identifier_ending_in_q_is_not_flagged():
    assert find_alt_quote_literals("SELECT freq FROM t WHERE x = 'a';\n") == []


def test_real_open_source_utplsql_q_literals_are_flagged():
    # Real shape from utPLSQL (source/create_synonyms.sql): several
    # q-literals concatenated across lines, with ordinary quoted strings
    # nested inside them. 706 such literals were found across the corpus.
    source = (
        "  when upper('&&ut3_user') = 'PUBLIC' then q'[define action_type='or replace noneditionable public'\n"
        "]'||q'[define ut3_user=''\n"
        "]'||q'[define grantee='PUBLIC']'\n"
    )
    findings = find_alt_quote_literals(source)
    assert len(findings) == 3
    assert [f.line for f in findings] == [1, 2, 3]
