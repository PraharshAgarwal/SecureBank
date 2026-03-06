-- SecureBank Stored Functions (PostgreSQL)
-- Demonstrates: ACID Transactions, Concurrency Control, Stored Functions

-- Drop function if exists
DROP FUNCTION IF EXISTS TransferFunds(INTEGER, INTEGER, DECIMAL, OUT VARCHAR, OUT VARCHAR);

-- Function: Transfer Funds (ACID Transaction)
-- This function demonstrates:
-- 1. ACID Properties (Atomicity, Consistency, Isolation, Durability)
-- 2. Concurrency Control (SELECT ... FOR UPDATE - Row-level locking)
-- 3. Transaction Management (BEGIN, COMMIT, ROLLBACK)

CREATE OR REPLACE FUNCTION TransferFunds(
    p_from_account_id INTEGER,
    p_to_account_id INTEGER,
    p_amount DECIMAL(15, 2),
    OUT p_status VARCHAR(50),
    OUT p_message VARCHAR(255)
)
RETURNS RECORD
LANGUAGE plpgsql
AS $$
DECLARE
    v_from_balance DECIMAL(15, 2);
    v_to_balance DECIMAL(15, 2);
BEGIN
    -- Lock rows for update (Isolation - Concurrency Control)
    -- This prevents other transactions from modifying these accounts simultaneously
    SELECT balance INTO v_from_balance
    FROM Accounts
    WHERE account_id = p_from_account_id
    FOR UPDATE;  -- Row-level lock for concurrency control

    SELECT balance INTO v_to_balance
    FROM Accounts
    WHERE account_id = p_to_account_id
    FOR UPDATE;  -- Row-level lock for concurrency control

    -- Validation Checks (Consistency)
    -- Note: In PostgreSQL, functions run within a transaction context
    -- Early returns will cause the transaction to rollback if called from app
    IF v_from_balance IS NULL THEN
        p_status := 'Failed';
        p_message := 'Source account not found.';
        RETURN;
    END IF;

    IF v_to_balance IS NULL THEN
        p_status := 'Failed';
        p_message := 'Destination account not found.';
        RETURN;
    END IF;

    IF p_amount <= 0 THEN
        p_status := 'Failed';
        p_message := 'Transfer amount must be greater than zero.';
        RETURN;
    END IF;

    IF v_from_balance < p_amount THEN
        p_status := 'Failed';
        p_message := 'Insufficient balance. Transaction rolled back.';
        RETURN;
    END IF;

    -- Perform the transfer (Atomic operation)
    UPDATE Accounts
    SET balance = balance - p_amount
    WHERE account_id = p_from_account_id;

    UPDATE Accounts
    SET balance = balance + p_amount
    WHERE account_id = p_to_account_id;

    -- Record transaction in history
    INSERT INTO TransactionHistory (
        from_account_id,
        to_account_id,
        transaction_type,
        amount,
        status
    ) VALUES (
        p_from_account_id,
        p_to_account_id,
        'Transfer',
        p_amount,
        'Success'
    );

    -- Set success status
    p_status := 'Success';
    p_message := 'Successfully transferred ₹' || p_amount || ' from Account #' || p_from_account_id || ' to Account #' || p_to_account_id;

EXCEPTION
    WHEN OTHERS THEN
        -- On error, set failure status and return cleanly
        -- The caller (app.py) will handle rollback
        p_status := 'Failed';
        p_message := 'Transaction failed due to database error. All changes rolled back.';
END;
$$;
