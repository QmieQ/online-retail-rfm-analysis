-- MySQL 8.0。由脚本在本项目独立实例中执行，不连接现有 MySQL 服务。
CREATE DATABASE IF NOT EXISTS retail_training CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_bin;
USE retail_training;
DROP TABLE IF EXISTS staging;
CREATE TABLE staging (
 source_row INT PRIMARY KEY,
 invoice_no VARCHAR(32), stock_code VARCHAR(32), description VARCHAR(255),
 quantity BIGINT, invoice_date DATETIME, unit_price_units BIGINT,
 customer_id VARCHAR(32), country VARCHAR(100)
);
-- TSV 由 Python 仅规范类型，不事先去重或筛选，NULL 用 \N。
-- 金额万分之一英镑整数存储，以避免浮点误差及过早四舍五入。
