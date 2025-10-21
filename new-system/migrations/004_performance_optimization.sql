-- new-system/migrations/004_performance_optimization.sql
-- This script creates materialized views for faster read performance on common queries.

-- 1. Materialized view for daily account balances.
-- This is incredibly useful for generating balance sheets or trial balances as of a certain date
-- without having to recalculate from the beginning of time.

CREATE MATERIALIZED VIEW IF NOT EXISTS account_balances_daily AS
SELECT
    company_id,
    account_id,
    transaction_date,
    sum(debit - credit) as daily_change,
    -- This running total is complex and might be better handled in the application layer
    -- or with a more advanced window function setup depending on the DB version.
    -- For simplicity, we'll calculate daily change and aggregate in the app.
    count() as transaction_count
FROM journal_entries_v2
WHERE is_posted = true -- Assuming an 'is_posted' flag exists or is added
GROUP BY company_id, account_id, transaction_date;

CREATE UNIQUE INDEX IF NOT EXISTS idx_account_balances_daily_unique
ON account_balances_daily (company_id, account_id, transaction_date);

-- 2. Function and cron job to refresh the materialized view nightly.
-- Using pg_cron extension is a common way to schedule this.

CREATE OR REPLACE FUNCTION refresh_daily_balances()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY account_balances_daily;
    -- CONCURRENTLY allows reads while the view is being refreshed, but requires a UNIQUE INDEX.
END;
$$ LANGUAGE plpgsql;

-- Schedule the refresh to run every night at 1 AM server time.
-- This requires the pg_cron extension to be installed and configured in PostgreSQL.
-- SELECT cron.schedule('nightly-balance-refresh', '0 1 * * *', 'SELECT refresh_daily_balances();');


-- 3. Add more specific indexes for common query patterns.
-- For example, fetching all transactions for a specific account in a date range.
CREATE INDEX IF NOT EXISTS idx_journal_entries_account_date_range
ON journal_entries_v2 (account_id, transaction_date DESC);

-- Index for fetching transactions of a certain type (e.g., for VAT reports)
-- This assumes you add a 'transaction_type' column to journal_entries_v2
-- CREATE INDEX IF NOT EXISTS idx_journal_entries_type_date
-- ON journal_entries_v2 (company_id, transaction_type, transaction_date);
