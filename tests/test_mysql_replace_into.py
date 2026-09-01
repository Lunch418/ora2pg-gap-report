from ora2pg_gap_report.detectors.mysql_replace_into import find_mysql_replace_into


def test_replace_into_is_flagged():
    source = (
        "CREATE PROCEDURE put_cache(IN p_k VARCHAR(50), IN p_v INT)\n"
        "BEGIN\n"
        "  REPLACE INTO cache1 (k, v) VALUES (p_k, p_v);\n"
        "END;\n"
    )
    findings = find_mysql_replace_into(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PUT_CACHE"
    assert findings[0].snippet == "REPLACE INTO"
    assert findings[0].severity == "high"
    assert findings[0].line == 3


def test_the_replace_string_function_is_not_flagged():
    # REPLACE(str, from, to) is an entirely different thing and converts
    # fine -- requiring INTO in the match is what keeps them apart.
    source = "CREATE PROCEDURE p() BEGIN SELECT REPLACE(s, 'a', 'b') FROM t; END;\n"
    assert find_mysql_replace_into(source) == []


def test_a_plain_insert_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN INSERT INTO t (id) VALUES (1); END;\n"
    assert find_mysql_replace_into(source) == []


def test_the_phrase_inside_a_string_literal_is_not_flagged():
    source = "CREATE PROCEDURE p() BEGIN SELECT 'REPLACE INTO t'; END;\n"
    assert find_mysql_replace_into(source) == []
