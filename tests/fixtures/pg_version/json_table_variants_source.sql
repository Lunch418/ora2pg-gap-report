CREATE OR REPLACE PROCEDURE gx_jt_nested(p_count OUT NUMBER) IS
  v_count NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count
  FROM JSON_TABLE(
      '{"order":1,"items":[{"sku":"a"},{"sku":"b"},{"sku":"c"}]}',
      '$'
      COLUMNS (
          order_id NUMBER PATH '$.order',
          NESTED PATH '$.items[*]' COLUMNS (sku VARCHAR2(10) PATH '$.sku')
      )
  );
  p_count := v_count;
END;
/
CREATE OR REPLACE PROCEDURE gx_jt_onerror(p_count OUT NUMBER) IS
  v_count NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count
  FROM JSON_TABLE(
      '[{"id":1},{"id":2}]',
      '$[*]' ERROR ON ERROR
      COLUMNS (id NUMBER PATH '$.id')
  );
  p_count := v_count;
END;
/
