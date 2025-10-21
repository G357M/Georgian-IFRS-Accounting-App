-- migrations/001_new_schema.sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Enum for account types for better data integrity
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'account_type_enum') THEN
        CREATE TYPE account_type_enum AS ENUM ('ASSET', 'LIABILITY', 'EQUITY', 'REVENUE', 'EXPENSE');
    END IF;
END$$;


-- Новая таблица счетов с UUID
CREATE TABLE accounts_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL, -- For multi-tenancy
    code VARCHAR(20) NOT NULL,
    name VARCHAR(100) NOT NULL,
    account_type account_type_enum NOT NULL,
    parent_id UUID REFERENCES accounts_v2(id),
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    
    -- Индексы для производительности
    CONSTRAINT unique_code_per_company UNIQUE (code, company_id)
);

CREATE INDEX idx_accounts_v2_company_id ON accounts_v2(company_id);
CREATE INDEX idx_accounts_v2_code ON accounts_v2(code);
CREATE INDEX idx_accounts_v2_type ON accounts_v2(account_type);
CREATE INDEX idx_accounts_v2_parent ON accounts_v2(parent_id);

-- Партиционирование журнала проводок по месяцам
CREATE TABLE journal_entries_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL,
    transaction_id UUID NOT NULL,
    account_id UUID NOT NULL REFERENCES accounts_v2(id),
    debit DECIMAL(15,2) DEFAULT 0.00,
    credit DECIMAL(15,2) DEFAULT 0.00,
    currency_code CHAR(3) NOT NULL DEFAULT 'GEL',
    exchange_rate DECIMAL(15,5) DEFAULT 1.00000,
    description TEXT,
    transaction_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    CONSTRAINT check_debit_credit CHECK (
        (debit >= 0 AND credit = 0) OR (credit >= 0 AND debit = 0)
    )
) PARTITION BY RANGE (transaction_date);

-- Создание партиций на год вперед (example for 2025)
CREATE TABLE journal_entries_202501 PARTITION OF journal_entries_v2
    FOR VALUES FROM ('2025-01-01') TO ('2025-02-01');
CREATE TABLE journal_entries_202502 PARTITION OF journal_entries_v2
    FOR VALUES FROM ('2025-02-01') TO ('2025-03-01');
-- ... create partitions for the rest of the year as needed
CREATE TABLE journal_entries_202503 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-03-01') TO ('2025-04-01');
CREATE TABLE journal_entries_202504 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-04-01') TO ('2025-05-01');
CREATE TABLE journal_entries_202505 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-05-01') TO ('2025-06-01');
CREATE TABLE journal_entries_202506 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');
CREATE TABLE journal_entries_202507 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');
CREATE TABLE journal_entries_202508 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');
CREATE TABLE journal_entries_202509 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
CREATE TABLE journal_entries_202510 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-10-01') TO ('2025-11-01');
CREATE TABLE journal_entries_202511 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-11-01') TO ('2025-12-01');
CREATE TABLE journal_entries_202512 PARTITION OF journal_entries_v2 FOR VALUES FROM ('2025-12-01') TO ('2026-01-01');

-- Index for the partitioned table
CREATE INDEX idx_journal_entries_v2_company_id_date ON journal_entries_v2(company_id, transaction_date);
CREATE INDEX idx_journal_entries_v2_account_id ON journal_entries_v2(account_id);
