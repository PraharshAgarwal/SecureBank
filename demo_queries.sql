-- SecureBank Demo Queries for Viva/Evaluation
-- Use these queries to demonstrate database features during evaluation

-- 1. Show all customers and their accounts (JOIN demonstration)
SELECT 
    c.customer_id,
    c.full_name,
    c.email,
    a.account_id,
    a.account_type,
    a.balance
FROM Customers c
INNER JOIN Accounts a ON c.customer_id = a.customer_id
ORDER BY c.customer_id, a.account_id;

-- 2. Show transaction history with account details (Multiple JOINs)
SELECT 
    th.transaction_id,
    th.transaction_timestamp,
    th.transaction_type,
    th.amount,
    th.status,
    fa.account_id AS from_account,
    ta.account_id AS to_account,
    fc.full_name AS from_customer,
    tc.full_name AS to_customer
FROM TransactionHistory th
LEFT JOIN Accounts fa ON th.from_account_id = fa.account_id
LEFT JOIN Accounts ta ON th.to_account_id = ta.account_id
LEFT JOIN Customers fc ON fa.customer_id = fc.customer_id
LEFT JOIN Customers tc ON ta.customer_id = tc.customer_id
ORDER BY th.transaction_timestamp DESC;

-- 3. Show audit log (Trigger demonstration)
SELECT 
    log_id,
    action_type,
    account_id,
    details,
    log_timestamp
FROM AuditLog
ORDER BY log_timestamp DESC
LIMIT 20;

-- 4. Show account balances (Current state)
SELECT 
    a.account_id,
    a.account_type,
    a.balance,
    c.full_name AS customer_name
FROM Accounts a
JOIN Customers c ON a.customer_id = c.customer_id
ORDER BY a.account_id;

-- 5. Show index usage (Explain plan for indexed query)
EXPLAIN SELECT 
    transaction_id,
    transaction_timestamp,
    amount,
    status
FROM TransactionHistory
WHERE transaction_timestamp >= CURRENT_TIMESTAMP - INTERVAL '30 days'
ORDER BY transaction_timestamp DESC;

-- 6. Show stored function definition (PostgreSQL)
SELECT pg_get_functiondef(oid) AS function_definition
FROM pg_proc
WHERE proname = 'transferfunds';

-- 7. Show trigger definitions (PostgreSQL)
SELECT 
    trigger_name,
    event_manipulation,
    event_object_table,
    action_statement
FROM information_schema.triggers
WHERE trigger_schema = 'public';

-- 8. Show all indexes in the database (PostgreSQL)
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
ORDER BY tablename, indexname;

-- 9. Test transaction with rollback (for demonstration)
-- This shows ACID properties — the CHECK (balance >= 0) constraint
-- will reject the UPDATE, triggering a rollback.
START TRANSACTION;

SELECT balance FROM Accounts WHERE account_id = 1 FOR UPDATE;

-- Try to transfer more than balance (will fail due to CHECK constraint)
UPDATE Accounts SET balance = balance - 10000 WHERE account_id = 1;

-- Check if it worked (it won't — CHECK constraint rejects negative balance)
SELECT balance FROM Accounts WHERE account_id = 1;

ROLLBACK;  -- Rollback the transaction

-- Verify balance is unchanged
SELECT balance FROM Accounts WHERE account_id = 1;


-- ============================================================
-- NEW: Views & Materialized Views
-- ============================================================

-- 10. Query the Customer Account Summary View
-- Demonstrates: SQL View with GROUP BY, COUNT, SUM
SELECT * FROM vw_customer_account_summary;

-- 11. Query the Transaction Details View (multi-JOIN)
-- Demonstrates: SQL View joining 4 tables
SELECT * FROM vw_transaction_details
ORDER BY transaction_timestamp DESC
LIMIT 10;

-- 12. Query the Materialized View for monthly analytics
-- Demonstrates: Materialized View with pre-computed aggregates
SELECT * FROM mv_monthly_transaction_summary ORDER BY month DESC;

-- 13. Refresh the Materialized View
-- Demonstrates: REFRESH MATERIALIZED VIEW CONCURRENTLY
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_monthly_transaction_summary;


-- ============================================================
-- NEW: Cursor-Based Paginated Statement
-- ============================================================

-- 14. Call cursor-based function (Page 1, 10 rows per page)
-- Demonstrates: PL/pgSQL Cursors (DECLARE, OPEN, FETCH, MOVE, CLOSE)
SELECT * FROM GetPaginatedStatement(1, 1, 10);

-- 15. Call cursor-based function (Page 2)
SELECT * FROM GetPaginatedStatement(1, 2, 10);


-- ============================================================
-- NEW: Window Functions
-- ============================================================

-- 16. Account Rankings using RANK() and DENSE_RANK()
-- Demonstrates: Window Functions without GROUP BY
SELECT
    c.full_name,
    a.account_type,
    a.balance,
    RANK()       OVER (ORDER BY a.balance DESC) AS balance_rank,
    DENSE_RANK() OVER (ORDER BY a.balance DESC) AS balance_dense_rank
FROM Accounts a
JOIN Customers c ON a.customer_id = c.customer_id
ORDER BY balance_rank;

-- 17. Top Transactions using ROW_NUMBER()
-- Demonstrates: ROW_NUMBER() Window Function combined with View
SELECT
    ROW_NUMBER() OVER (ORDER BY amount DESC) AS row_num,
    transaction_id,
    amount,
    from_customer_name,
    to_customer_name,
    transaction_timestamp
FROM vw_transaction_details
ORDER BY amount DESC
LIMIT 10;

-- 18. Explain plan on View query (shows how PostgreSQL optimizes views)
EXPLAIN ANALYZE SELECT * FROM vw_customer_account_summary;
