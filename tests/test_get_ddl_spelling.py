"""DBMS_METADATA.GET_DDL -- what ora2pg-gap-export writes, and this tool's
documented Oracle input -- spells objects its own way: EDITIONABLE after
OR REPLACE on every editionable object, and every name schema-qualified
and double-quoted. Several patterns were only ever checked against
hand-written DDL and did not accept that spelling.

Found by running every Oracle gap's minimal example (docs/research) in a
real Oracle 23ai, exporting each schema back with ora2pg-gap-export and
scanning the export: standalone procedures and functions were never
recognised as objects (every finding in one came out UNKNOWN, and
nested_subprogram, which starts from the same pattern, found nothing),
private synonyms were never flagged, and neither were bitmap indexes.
The fixtures below are the export's text verbatim."""

from ora2pg_gap_report.core import count_objects, scan_source
from ora2pg_gap_report.detectors.connect_by import guess_object_type


def _found(source: str) -> list[tuple[str, str]]:
    # GET_DDL qualifies every name with its schema, which is GAP-124 in
    # every one of these; what these tests are about is the other finding.
    return sorted((f.detector, f.object_name) for f in scan_source(source) if f.detector != "schema_qualified_name")


GOTO_PROCEDURE = (
    '\n  CREATE OR REPLACE EDITIONABLE PROCEDURE "G063"."HOP" IS\n'
    "  i NUMBER := 0;\n"
    "BEGIN\n"
    "  <<again>>\n"
    "  i := i + 1;\n"
    "  IF i < 3 THEN\n"
    "    GOTO again;\n"
    "  END IF;\n"
    "END;"
)


def test_a_finding_in_an_exported_standalone_procedure_is_attributed_to_it():
    assert _found(GOTO_PROCEDURE) == [("goto_statement", "HOP"), ("number_without_precision", "HOP")]


def test_an_exported_standalone_procedure_is_counted_as_an_object():
    assert count_objects(GOTO_PROCEDURE) == 1


def test_a_nested_subprogram_in_an_exported_standalone_procedure_is_found():
    source = (
        '\n  CREATE OR REPLACE EDITIONABLE PROCEDURE "G034"."OUTER_PROC" AS\n'
        "  PROCEDURE inner_proc(p_val NUMBER) IS\n"
        "  BEGIN\n"
        "    DBMS_OUTPUT.PUT_LINE('inner: ' || p_val);\n"
        "  END;\n"
        "BEGIN\n"
        "  inner_proc(1);\n"
        "END;"
    )
    assert ("nested_subprogram", "OUTER_PROC.INNER_PROC") in _found(source)


def test_an_unquoted_schema_qualified_routine_is_named_after_itself_not_its_schema():
    source = "CREATE OR REPLACE PROCEDURE hr.hop IS\nBEGIN\n  GOTO x;\n  <<x>> NULL;\nEND;"
    assert _found(source) == [("goto_statement", "HOP")]


def test_an_exported_private_synonym_is_flagged():
    source = '\n  CREATE OR REPLACE EDITIONABLE SYNONYM "HR"."EMPS" FOR "HR"."EMPLOYEES"'
    assert _found(source) == [("public_synonym", "EMPS")]


def test_an_exported_bitmap_index_is_flagged():
    source = (
        '\n  CREATE BITMAP INDEX "G046"."IDX_EMP_GENDER" ON "G046"."EMP_IDX" ("GENDER") \n'
        "  PCTFREE 10 INITRANS 2 MAXTRANS 255 COMPUTE STATISTICS \n"
        '  TABLESPACE "USERS" '
    )
    # Named the way the hand-written spelling of the same qualified name
    # always was (schema.index), just without the quotes.
    assert _found(source) == [("bitmap_index", "G046.IDX_EMP_GENDER")]


def test_the_connect_by_check_runs_an_exported_routine_as_its_own_type():
    assert guess_object_type('CREATE OR REPLACE EDITIONABLE PROCEDURE "HR"."P" IS BEGIN NULL; END;') == "PROCEDURE"
    assert guess_object_type('CREATE OR REPLACE EDITIONABLE FUNCTION "HR"."F" RETURN NUMBER IS BEGIN RETURN 1; END;') == "FUNCTION"
    assert guess_object_type('CREATE OR REPLACE EDITIONABLE TRIGGER "HR"."T" BEFORE INSERT ON x BEGIN NULL; END;') == "TRIGGER"
    assert guess_object_type('CREATE OR REPLACE FORCE EDITIONABLE VIEW "HR"."V" AS SELECT 1 FROM dual') == "VIEW"
