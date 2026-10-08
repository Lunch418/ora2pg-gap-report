CREATE OR REPLACE PACKAGE file_pkg AS
  g_os_windows CONSTANT VARCHAR2(1) := 'w';
  g_mode CONSTANT NUMBER := 3;
  FUNCTION sep(p_os IN VARCHAR2 := g_os_windows) RETURN VARCHAR2;
END file_pkg;
/
CREATE OR REPLACE PACKAGE BODY fmt_pkg AS
  c_date CONSTANT VARCHAR2(30) := 'YYYY-MM-DD';
  c_stamp CONSTANT VARCHAR2(30) := c_date || ' HH24:MI';
  g_counter NUMBER := 0;
  FUNCTION date_fmt RETURN VARCHAR2 IS
  BEGIN
    RETURN c_date;
  END;
  FUNCTION stamp_fmt RETURN VARCHAR2 IS
  BEGIN
    RETURN c_stamp;
  END;
END fmt_pkg;
/
CREATE OR REPLACE PACKAGE BODY file_pkg AS
  FUNCTION sep(p_os IN VARCHAR2 := g_os_windows) RETURN VARCHAR2 IS
  BEGIN
    RETURN CASE WHEN p_os = g_os_windows THEN 'win' ELSE 'unix' END;
  END;
END file_pkg;
/
CREATE OR REPLACE TRIGGER gx_t_ai AFTER INSERT ON gx_orders
BEGIN
  UPDATE gx_fired SET n = n + 1;
END;
/
