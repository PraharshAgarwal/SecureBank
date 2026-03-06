-- SecureBank Database Triggers (PostgreSQL)
-- Demonstrates: Database Triggers, Audit Logging

-- Drop existing triggers and functions
DROP TRIGGER IF EXISTS audit_transfer_access ON TransactionHistory;
DROP TRIGGER IF EXISTS audit_balance_update ON Accounts;
DROP FUNCTION IF EXISTS audit_transfer_access_func();
DROP FUNCTION IF EXISTS audit_balance_update_func();

-- Trigger Function: Audit Log for Transfer Page Visits
-- This trigger automatically logs when someone accesses the transfer functionality
-- Demonstrates: Database Triggers, Automatic Logging

CREATE OR REPLACE FUNCTION audit_transfer_access_func()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    INSERT INTO AuditLog (
        action_type,
        account_id,
        details,
        log_timestamp
    ) VALUES (
        'Transfer Page Accessed',
        NEW.from_account_id,
        'Transfer initiated from Account #' || NEW.from_account_id || ' to Account #' || NEW.to_account_id,
        CURRENT_TIMESTAMP
    );
    RETURN NEW;
END;
$$;

-- Create trigger
CREATE TRIGGER audit_transfer_access
AFTER INSERT ON TransactionHistory
FOR EACH ROW
EXECUTE FUNCTION audit_transfer_access_func();

-- Trigger Function: Balance Update Audit
-- Logs whenever an account balance is updated
CREATE OR REPLACE FUNCTION audit_balance_update_func()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.balance != NEW.balance THEN
        INSERT INTO AuditLog (
            action_type,
            account_id,
            details,
            log_timestamp
        ) VALUES (
            'Balance Updated',
            NEW.account_id,
            'Balance changed from ₹' || OLD.balance || ' to ₹' || NEW.balance,
            CURRENT_TIMESTAMP
        );
    END IF;
    RETURN NEW;
END;
$$;

-- Create trigger
CREATE TRIGGER audit_balance_update
AFTER UPDATE ON Accounts
FOR EACH ROW
EXECUTE FUNCTION audit_balance_update_func();
