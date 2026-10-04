USE retail_training;
DROP TABLE IF EXISTS audit;
CREATE TABLE audit AS
WITH ranked AS (
 SELECT *, ROW_NUMBER() OVER (
  PARTITION BY invoice_no, stock_code, description, quantity,
               invoice_date, unit_price_units, customer_id, country
  ORDER BY source_row
 ) AS duplicate_rank
 FROM staging
)
SELECT *,
 CASE
  WHEN duplicate_rank > 1 THEN 'duplicate'
  WHEN invoice_no IS NULL OR stock_code IS NULL OR quantity IS NULL
    OR invoice_date IS NULL OR unit_price_units IS NULL THEN 'invalid_required'
  WHEN UPPER(LEFT(invoice_no, 1)) = 'C' THEN 'cancelled'
  WHEN quantity <= 0 THEN 'nonpositive_quantity'
  WHEN unit_price_units <= 0 THEN 'nonpositive_price'
  ELSE 'retained'
 END AS reason,
 quantity * unit_price_units AS amount_units,
 REGEXP_LIKE(stock_code, '^[0-9]{5}[A-Za-z]*$', 'c') AS is_merchandise
FROM ranked;
DROP TABLE IF EXISTS sales;
CREATE TABLE sales AS SELECT * FROM audit WHERE reason = 'retained';
CREATE INDEX idx_sales_invoice ON sales(invoice_no);
CREATE INDEX idx_sales_customer ON sales(customer_id);
