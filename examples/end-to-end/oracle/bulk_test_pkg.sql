CREATE OR REPLACE PACKAGE BODY bulk_test_pkg AS
  PROCEDURE archive_old_orders IS
    TYPE t_id_tab IS TABLE OF orders.order_id%TYPE;
    v_ids t_id_tab;
  BEGIN
    SELECT order_id
    BULK COLLECT INTO v_ids
    FROM orders
    WHERE status = 'CLOSED';

    FORALL i IN 1 .. v_ids.COUNT
      DELETE FROM orders WHERE order_id = v_ids(i);

    COMMIT;
  END archive_old_orders;
END bulk_test_pkg;
/
