CREATE OR REPLACE PROCEDURE gx_jt(p_count OUT NUMBER) IS
  v_count NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_count
  FROM JSON_TABLE(
      '[{"id":1,"amount":100},{"id":2,"amount":200}]',
      '$[*]'
      COLUMNS (
          id     NUMBER PATH '$.id',
          amount NUMBER PATH '$.amount'
      )
  );
  p_count := v_count;
END;
/
