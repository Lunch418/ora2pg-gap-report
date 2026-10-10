CREATE TABLE store (
  store_id INT NOT NULL,
  manager_id INT NOT NULL,
  PRIMARY KEY NONCLUSTERED (store_id)
)
GO
 CREATE  INDEX idx_fk_store_id ON store(store_id)
GO

CREATE TABLE staff (
  staff_id INT NOT NULL,
  store_id INT NOT NULL,
  amount INT NOT NULL,
  PRIMARY KEY NONCLUSTERED (staff_id),
)

CREATE TABLE customer (
  customer_id INT NOT NULL,
  store_id INT NOT NULL
)
GO
 CREATE  INDEX idx_fk_store_id ON staff(store_id)
GO
 CREATE  INDEX idx_fk_store_id ON customer(store_id)
GO
CREATE PROCEDURE staff_totals @store INT AS
BEGIN
  SELECT store_id, SUM(amount) AS total FROM staff GROUP BY store_id WITH ROLLUP;
END;
GO
