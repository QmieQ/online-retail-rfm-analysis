-- 可直接在项目数据库执行，用于理解 GROUP BY、COUNT DISTINCT 和窗口函数。
USE retail_training;
-- 月度销售额和订单平均金额。2011-12 为不完整月。
SELECT DATE_FORMAT(invoice_date, '%Y-%m') AS month,
 SUM(amount_units)/10000 AS sales_gbp,
 COUNT(DISTINCT invoice_no) AS orders,
 SUM(amount_units)/10000/COUNT(DISTINCT invoice_no) AS aov_gbp
FROM sales GROUP BY month ORDER BY month;

-- 商品贡献：运费、手续费等非标准商品代码不进入此排名。
SELECT stock_code, SUM(amount_units)/10000 AS sales_gbp,
 SUM(SUM(amount_units)) OVER (ORDER BY SUM(amount_units) DESC, stock_code
   ROWS UNBOUNDED PRECEDING) / SUM(SUM(amount_units)) OVER () AS cumulative_share
FROM sales WHERE is_merchandise = 1 GROUP BY stock_code
ORDER BY sales_gbp DESC, stock_code;

-- RFM 基础指标。F 是不同订单数，不是明细行数。
SET @reference_date = (SELECT DATE(MAX(invoice_date)) + INTERVAL 1 DAY FROM staging);
SELECT customer_id,
 DATEDIFF(@reference_date, DATE(MAX(invoice_date))) AS recency_days,
 COUNT(DISTINCT invoice_no) AS frequency,
 SUM(amount_units)/10000 AS monetary_gbp
FROM sales WHERE customer_id IS NOT NULL GROUP BY customer_id;
