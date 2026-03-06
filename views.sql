-- SecureBank Views & Materialized Views (PostgreSQL)
-- Demonstrates: SQL Views, Materialized Views, Aggregation, Multi-table JOINs

-- Drop existing views if they exist
DROP MATERIALIZED VIEW IF EXISTS mv_monthly_transaction_summary CASCADE;
DROP VIEW IF EXISTS vw_transaction_details CASCADE;
DROP VIEW IF EXISTS vw_customer_account_summary CASCADE;


-- ============================================================
-- View 1: Customer Account Summary
-- Aggregates customer data with their account statistics
-- Demonstrates: VIEW, LEFT JOIN, GROUP BY, COUNT, SUM, MIN
-- ============================================================
CREATE OR REPLACE VIEW vw_customer_account_summary AS
SELECT
    c.customer_id,
    c.full_name,
    c.email,
    c.phone,
    c.created_at AS member_since,
    COUNT(a.account_id)              AS total_accounts,
    COALESCE(SUM(a.balance), 0)      AS total_balance,
    COALESCE(MIN(a.balance), 0)      AS min_account_balance,
    COALESCE(MAX(a.balance), 0)      AS max_account_balance,
    MIN(a.created_at)                AS first_account_date
FROM Customers c
LEFT JOIN Accounts a ON c.customer_id = a.customer_id
GROUP BY c.customer_id, c.full_name, c.email, c.phone, c.created_at;

-- Usage: SELECT * FROM vw_customer_account_summary;


-- ============================================================
-- View 2: Transaction Details (Multi-JOIN View)
-- Flattens transaction data by joining 4 tables
-- Demonstrates: VIEW, LEFT JOIN across 4 tables, CASE expression
-- ============================================================
CREATE OR REPLACE VIEW vw_transaction_details AS
SELECT
    th.transaction_id,
    th.transaction_type,
    th.amount,
    th.status,
    th.transaction_timestamp,
    -- Source account info
    th.from_account_id,
    fa.account_number  AS from_account_number,
    fa.account_type    AS from_account_type,
    fc.full_name       AS from_customer_name,
    -- Destination account info
    th.to_account_id,
    ta.account_number  AS to_account_number,
    ta.account_type    AS to_account_type,
    tc.full_name       AS to_customer_name,
    -- Direction helper for display
    CASE
        WHEN th.from_account_id IS NULL THEN 'CREDIT'
        ELSE 'TRANSFER'
    END AS direction_type
FROM TransactionHistory th
LEFT JOIN Accounts fa  ON th.from_account_id = fa.account_id
LEFT JOIN Accounts ta  ON th.to_account_id   = ta.account_id
LEFT JOIN Customers fc ON fa.customer_id     = fc.customer_id
LEFT JOIN Customers tc ON ta.customer_id     = tc.customer_id;

-- Usage: SELECT * FROM vw_transaction_details ORDER BY transaction_timestamp DESC;


-- ============================================================
-- Materialized View: Monthly Transaction Summary
-- Pre-computed monthly aggregates for fast analytics
-- Demonstrates: MATERIALIZED VIEW, DATE_TRUNC, Conditional Aggregation
-- Must be refreshed with: REFRESH MATERIALIZED VIEW mv_monthly_transaction_summary;
-- ============================================================
CREATE MATERIALIZED VIEW mv_monthly_transaction_summary AS
SELECT
    DATE_TRUNC('month', th.transaction_timestamp)::DATE  AS month,
    COUNT(*)                                              AS total_transactions,
    SUM(th.amount)                                        AS total_volume,
    ROUND(AVG(th.amount), 2)                              AS avg_transaction_amount,
    MAX(th.amount)                                        AS largest_transaction,
    MIN(th.amount)                                        AS smallest_transaction,
    COUNT(CASE WHEN th.status = 'Success' THEN 1 END)    AS successful_count,
    COUNT(CASE WHEN th.status = 'Failed'  THEN 1 END)    AS failed_count,
    COUNT(DISTINCT th.from_account_id)                    AS unique_senders,
    COUNT(DISTINCT th.to_account_id)                      AS unique_receivers
FROM TransactionHistory th
GROUP BY DATE_TRUNC('month', th.transaction_timestamp)
ORDER BY month DESC;

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX idx_mv_monthly_month
    ON mv_monthly_transaction_summary(month);

-- Usage:
-- SELECT * FROM mv_monthly_transaction_summary;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_monthly_transaction_summary;
