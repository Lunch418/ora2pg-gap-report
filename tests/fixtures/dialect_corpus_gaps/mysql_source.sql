CREATE TABLE payment (store_id INT NOT NULL, amount INT NOT NULL);
CREATE VIEW payment_totals AS SELECT store_id, SUM(amount) AS total FROM payment GROUP BY store_id WITH ROLLUP;
