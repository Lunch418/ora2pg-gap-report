-- Minimal stub tables for docs/research/samples/ trigger fixtures.
--
-- Packages tolerate missing table dependencies fine (Oracle still creates
-- them, just marks them INVALID — DBMS_METADATA.GET_DDL still returns the
-- source regardless), so none of the package samples need anything here.
-- Triggers are different: CREATE TRIGGER validates its target table's
-- existence immediately, as a structural DDL requirement, not just a
-- compile-time reference — so those need real (if minimal) tables first.

CREATE TABLE employees (
    employee_id NUMBER PRIMARY KEY,
    manager_id  NUMBER,
    last_name   VARCHAR2(100),
    salary      NUMBER
);

CREATE TABLE mfe_customers (
    id NUMBER PRIMARY KEY
);

CREATE TABLE constructors (
    id NUMBER PRIMARY KEY
);

CREATE TABLE constructors_jn (
    id NUMBER PRIMARY KEY
);
