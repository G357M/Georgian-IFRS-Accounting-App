-- This schema is designed for high-performance analytics in ClickHouse.

-- 1. Main table for raw transaction events, optimized for fast writes.
CREATE TABLE IF NOT EXISTS transactions_raw_events (
    event_id UUID,
    transaction_id UUID,
    event_type String,
    event_timestamp DateTime,
    company_id UUID,
    user_id UUID,
    payload String -- JSON as a string
) ENGINE = Kafka(
    'kafka:9092',
    'accounting.transactioncreated,accounting.transactionapproved,accounting.transactionposted',
    'clickhouse_consumers_group1',
    'JSONAsString'
);

-- 2. Materialized view to parse raw events and populate an analytics-friendly table.
CREATE TABLE IF NOT EXISTS transactions_analytics (
    transaction_id UUID,
    transaction_date Date,
    transaction_timestamp DateTime,
    company_id UUID,
    user_id UUID,
    total_amount Decimal(15, 2),
    currency_code String,
    status Enum8('draft' = 1, 'approved' = 2, 'posted' = 3),
    last_updated DateTime
) ENGINE = ReplacingMergeTree(last_updated)
PARTITION BY toYYYYMM(transaction_date)
ORDER BY (company_id, transaction_date, transaction_id);

CREATE MATERIALIZED VIEW IF NOT EXISTS transactions_mv TO transactions_analytics AS
SELECT
    JSONExtractUUID(payload, 'aggregate_id') AS transaction_id,
    toDate(JSONExtractString(payload, 'timestamp')) AS transaction_date,
    toDateTime(JSONExtractString(payload, 'timestamp')) AS transaction_timestamp,
    JSONExtractUUID(payload, 'metadata', 'company_id') AS company_id,
    JSONExtractUUID(payload, 'metadata', 'user_id') AS user_id,
    JSONExtractDecimal(payload, 'event_data', 'total_amount', 15, 2) AS total_amount,
    'GEL' as currency_code, -- Assuming GEL, could be extracted if available
    if(JSONExtractString(payload, 'event_type') = 'TransactionPosted', 'posted',
       if(JSONExtractString(payload, 'event_type') = 'TransactionApproved', 'approved', 'draft')) as status,
    now() as last_updated
FROM transactions_raw_events;

-- 3. Materialized view for real-time daily KPI aggregation.
CREATE TABLE IF NOT EXISTS daily_kpi_summary (
    company_id UUID,
    kpi_date Date,
    transaction_count AggregateFunction(count),
    total_volume AggregateFunction(sum, Decimal(15, 2)),
    avg_transaction_value AggregateFunction(avg, Decimal(15, 2))
) ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(kpi_date)
ORDER BY (company_id, kpi_date);

CREATE MATERIALIZED VIEW IF NOT EXISTS daily_kpi_mv TO daily_kpi_summary AS
SELECT
    company_id,
    transaction_date as kpi_date,
    countState() as transaction_count,
    sumState(total_amount) as total_volume,
    avgState(total_amount) as avg_transaction_value
FROM transactions_analytics
WHERE status = 'posted'
GROUP BY company_id, kpi_date;
