CREATE OR REPLACE FUNCTION gx_c1(a_item VARCHAR2, a_c VARCHAR2:= '.', a_base INTEGER :=0) RETURN VARCHAR2 IS
BEGIN
  RETURN trim(leading a_c from a_item) || '|' || trim(trailing a_c from a_item) || '|' || a_base;
END;
/
CREATE OR REPLACE PROCEDURE gx_c2(p_text VARCHAR2 DEFAULT NULL, p_id OUT NUMBER) IS
BEGIN
  p_id := NVL(LENGTH(p_text), 0);
END;
/
CREATE OR REPLACE FUNCTION gx_c3(p NUMBER) RETURN NUMBER IS
  n#count NUMBER(5) := p;
BEGIN
  RETURN n#count * 2;
END;
/
CREATE OR REPLACE FUNCTION gx_c4(p_xml XMLTYPE) RETURN VARCHAR2 IS
BEGIN
  RETURN p_xml.extract('/a/text()').getstringval();
END;
/
