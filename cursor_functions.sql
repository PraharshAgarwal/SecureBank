-- SecureBank Cursor-Based Pagination (PostgreSQL)
-- Demonstrates: PL/pgSQL Cursors (DECLARE, OPEN, FETCH, MOVE, CLOSE)

DROP FUNCTION IF EXISTS GetPaginatedStatement(INTEGER, INTEGER, INTEGER);


-- ============================================================
-- Function: GetPaginatedStatement
-- Returns a paginated bank statement for a given account
--
-- Demonstrates:
--   1. DECLARE CURSOR — defines a scrollable result set
--   2. OPEN          — opens the cursor for traversal
--   3. MOVE FORWARD  — skips rows for offset-based pagination
--   4. FETCH         — retrieves one row at a time
--   5. CLOSE         — releases cursor resources
--   6. RETURN NEXT   — builds the result set row by row
--
-- Parameters:
--   p_account_id  — the account to generate a statement for
--   p_page        — which page of results (1-based)
--   p_page_size   — how many rows per page (default 10)
-- ============================================================
CREATE OR REPLACE FUNCTION GetPaginatedStatement(
    p_account_id  INTEGER,
    p_page        INTEGER DEFAULT 1,
    p_page_size   INTEGER DEFAULT 10
)
RETURNS TABLE (
    row_num           INTEGER,
    transaction_id    INTEGER,
    transaction_type  VARCHAR,
    amount            DECIMAL,
    status            VARCHAR,
    transaction_date  TIMESTAMP,
    counterparty      VARCHAR,
    direction         VARCHAR,
    total_records     INTEGER,
    total_pages       INTEGER
)
LANGUAGE plpgsql
AS $$
DECLARE
    -- -------------------------------------------------------
    -- DECLARE CURSOR: defines the full result set to paginate
    -- The cursor fetches all transactions for this account,
    -- joined with account and customer tables for context.
    -- -------------------------------------------------------
    stmt_cursor CURSOR FOR
        SELECT
            th.transaction_id,
            th.transaction_type,
            th.amount,
            th.status,
            th.transaction_timestamp,
            CASE
                WHEN th.from_account_id = p_account_id
                    THEN COALESCE(tc.full_name, 'External')
                ELSE COALESCE(fc.full_name, 'External')
            END AS counterparty_name,
            CASE
                WHEN th.from_account_id = p_account_id THEN 'DEBIT'
                ELSE 'CREDIT'
            END AS txn_direction
        FROM TransactionHistory th
        LEFT JOIN Accounts fa  ON th.from_account_id = fa.account_id
        LEFT JOIN Accounts ta  ON th.to_account_id   = ta.account_id
        LEFT JOIN Customers fc ON fa.customer_id     = fc.customer_id
        LEFT JOIN Customers tc ON ta.customer_id     = tc.customer_id
        WHERE th.from_account_id = p_account_id
           OR th.to_account_id   = p_account_id
        ORDER BY th.transaction_timestamp DESC;

    v_record       RECORD;
    v_total        INTEGER;
    v_pages        INTEGER;
    v_offset       INTEGER;
    v_fetched      INTEGER := 0;
    v_row          INTEGER;
BEGIN
    -- Count total records for this account
    SELECT COUNT(*) INTO v_total
    FROM TransactionHistory
    WHERE from_account_id = p_account_id
       OR to_account_id   = p_account_id;

    -- Calculate total pages
    v_pages  := CEIL(v_total::DECIMAL / p_page_size);
    v_offset := (p_page - 1) * p_page_size;
    v_row    := v_offset;

    -- -------------------------------------------------------
    -- OPEN CURSOR: begin traversal of the result set
    -- -------------------------------------------------------
    OPEN stmt_cursor;

    -- -------------------------------------------------------
    -- MOVE FORWARD: skip rows to reach the requested page
    -- This is how cursor-based pagination works — we advance
    -- past the rows belonging to previous pages.
    -- -------------------------------------------------------
    IF v_offset > 0 THEN
        MOVE FORWARD v_offset IN stmt_cursor;
    END IF;

    -- -------------------------------------------------------
    -- FETCH loop: retrieve exactly p_page_size rows
    -- Each FETCH pulls one row from the cursor position.
    -- -------------------------------------------------------
    LOOP
        FETCH stmt_cursor INTO v_record;
        EXIT WHEN NOT FOUND OR v_fetched >= p_page_size;

        v_row     := v_row + 1;
        v_fetched := v_fetched + 1;

        -- Map cursor record to output columns
        row_num          := v_row;
        transaction_id   := v_record.transaction_id;
        transaction_type := v_record.transaction_type;
        amount           := v_record.amount;
        status           := v_record.status;
        transaction_date := v_record.transaction_timestamp;
        counterparty     := v_record.counterparty_name;
        direction        := v_record.txn_direction;
        total_records    := v_total;
        total_pages      := v_pages;

        -- Build the result set one row at a time
        RETURN NEXT;
    END LOOP;

    -- -------------------------------------------------------
    -- CLOSE CURSOR: release resources
    -- -------------------------------------------------------
    CLOSE stmt_cursor;
END;
$$;

-- Usage:
-- Page 1 (10 rows): SELECT * FROM GetPaginatedStatement(1, 1, 10);
-- Page 2 (10 rows): SELECT * FROM GetPaginatedStatement(1, 2, 10);
