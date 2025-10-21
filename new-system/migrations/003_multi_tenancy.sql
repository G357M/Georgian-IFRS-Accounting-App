-- migrations/003_multi_tenancy.sql
-- This script adapts the schema for multi-tenancy.
-- It assumes that 'company_id' from the previous script will be used as the 'tenant_id'.

-- 1. Add a table for tenants (companies)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    status VARCHAR(50) DEFAULT 'active', -- e.g., active, suspended, trial
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE UNIQUE INDEX idx_tenants_name ON tenants(name);

-- 2. Ensure all relevant tables have a tenant_id column.
-- The 'accounts_v2' and 'journal_entries_v2' tables from '001_new_schema.sql'
-- already include a 'company_id' which we will use as the tenant_id.
-- Let's ensure it's properly constrained.

-- Add foreign key constraint to accounts_v2
ALTER TABLE accounts_v2
ADD CONSTRAINT fk_accounts_tenant
FOREIGN KEY (company_id) REFERENCES tenants(id) ON DELETE CASCADE;

-- Add foreign key constraint to journal_entries_v2
ALTER TABLE journal_entries_v2
ADD CONSTRAINT fk_journal_entries_tenant
FOREIGN KEY (company_id) REFERENCES tenants(id) ON DELETE CASCADE;


-- 3. Implement Row-Level Security (RLS) for data isolation.

-- Enable RLS on the tables
ALTER TABLE accounts_v2 ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries_v2 ENABLE ROW LEVEL SECURITY;
-- Add other tables as needed, e.g., users, transactions, etc.

-- Create a reusable function to get the current tenant_id from the session settings
CREATE OR REPLACE FUNCTION get_current_tenant_id()
RETURNS UUID AS $$
BEGIN
    RETURN current_setting('app.current_tenant_id', true)::UUID;
EXCEPTION
    WHEN UNDEFINED_OBJECT THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Create policies to enforce tenant isolation
-- Policy for accounts
CREATE POLICY accounts_tenant_isolation_policy
ON accounts_v2
FOR ALL
USING (company_id = get_current_tenant_id());

-- Policy for journal entries
CREATE POLICY journal_entries_tenant_isolation_policy
ON journal_entries_v2
FOR ALL
USING (company_id = get_current_tenant_id());

-- Note: To use RLS, your application's database connection must set the
-- 'app.current_tenant_id' session variable for each request.
-- For example, after a user authenticates:
--
-- async with db_pool.acquire() as conn:
--     await conn.execute(f"SET app.current_tenant_id = '{user.tenant_id}'")
--     # ... proceed with user's query
--
-- This ensures that all subsequent queries in that session are automatically
-- filtered for the correct tenant.
