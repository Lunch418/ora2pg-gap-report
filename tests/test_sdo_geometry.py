from ora2pg_gap_report.detectors.sdo_geometry import find_sdo_geometry_columns


def test_a_qualified_sdo_geometry_column_is_flagged():
    source = (
        "CREATE TABLE places (\n"
        "    id  NUMBER PRIMARY KEY,\n"
        "    geo MDSYS.SDO_GEOMETRY\n"
        ");\n"
    )
    findings = find_sdo_geometry_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "PLACES"
    assert findings[0].snippet == "SDO_GEOMETRY"
    assert findings[0].line == 3


def test_the_severity_is_medium_not_high():
    # Deliberate: ora2pg picks the right target type and only omits the
    # CREATE EXTENSION line, so one line fixes it.
    source = "CREATE TABLE t (geo SDO_GEOMETRY);\n"
    assert find_sdo_geometry_columns(source)[0].severity == "medium"


def test_the_unqualified_spelling_is_flagged():
    assert len(find_sdo_geometry_columns("CREATE TABLE t (geo SDO_GEOMETRY);\n")) == 1


def test_an_ordinary_column_list_is_not_flagged():
    assert find_sdo_geometry_columns("CREATE TABLE t (id NUMBER, name VARCHAR2(30));\n") == []


def test_a_similarly_named_column_is_not_flagged():
    assert find_sdo_geometry_columns("CREATE TABLE t (sdo_geometry_id NUMBER);\n") == []


def test_real_oracle_sample_schema_warehouses_is_flagged():
    # Real shape from Oracle's own db-sample-schemas
    # (order_entry/cwhs_v3.sql): a spatial column in the middle of an
    # otherwise ordinary table.
    source = (
        "CREATE TABLE warehouses\n"
        "    ( warehouse_id   NUMBER(3)\n"
        "    , warehouse_spec XMLTYPE\n"
        "    , warehouse_name VARCHAR2(35)\n"
        "    , location_id    NUMBER(4)\n"
        "    , wh_geo_location MDSYS.SDO_GEOMETRY\n"
        "    ) ;\n"
    )
    findings = find_sdo_geometry_columns(source)
    assert len(findings) == 1
    assert findings[0].object_name == "WAREHOUSES"
    assert findings[0].line == 6
