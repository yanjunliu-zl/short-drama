-- ClickHouse initialization — Short Drama Platform
CREATE DATABASE IF NOT EXISTS shortdrama;

-- User behavior event log (immutable, append-only)
CREATE TABLE IF NOT EXISTS shortdrama.user_events (
    event_time  DateTime64(3)  DEFAULT now64(3),
    event_type  LowCardinality(String),   -- view / like / share / skip / search / generate
    user_id     String,
    item_id     String,
    query       String DEFAULT '',         -- search query (for search events)
    recall_source String DEFAULT '',       -- cf / content / hot / author / search / embedding
    position    UInt16 DEFAULT 0,          -- position in result list
    dwell_ms    UInt32 DEFAULT 0,          -- dwell time in ms
    session_id  String DEFAULT '',
    metadata    String DEFAULT '{}'        -- JSON for extensible fields
) ENGINE = MergeTree()
PARTITION BY toYYYYMMDD(event_time)
ORDER BY (event_type, user_id, event_time)
TTL event_time + INTERVAL 90 DAY
SETTINGS index_granularity = 8192;

-- Search funnel aggregation (materialized view)
CREATE MATERIALIZED VIEW IF NOT EXISTS shortdrama.search_funnel_hourly
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMMDD(date)
ORDER BY (date, hour, query)
AS SELECT
    toDate(event_time) AS date,
    toHour(event_time) AS hour,
    query,
    countIf(event_type = 'search') AS impressions,
    countIf(event_type = 'click')  AS clicks,
    uniqExactIf(user_id, event_type = 'search') AS unique_searchers,
    uniqExactIf(user_id, event_type = 'click')  AS unique_clickers
FROM shortdrama.user_events
WHERE event_type IN ('search', 'click')
GROUP BY date, hour, query;

-- LLM usage tracking (replace MySQL generation_tasks for analytics)
CREATE TABLE IF NOT EXISTS shortdrama.llm_usage (
    event_time   DateTime64(3) DEFAULT now64(3),
    service_name LowCardinality(String),   -- script-service / storyboard-service / llmhua-service
    model_name   LowCardinality(String),   -- deepseek-chat / gpt-4o / claude-sonnet-5
    endpoint     String,                   -- /generate/from-outline-sync / shots/generate
    user_id      String,
    tokens_in    UInt32,
    tokens_out   UInt32,
    duration_ms  UInt32,
    cost_rmb     Float64,
    cache_hit    UInt8 DEFAULT 0           -- 0=miss, 1=hit
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(event_time)
ORDER BY (service_name, model_name, event_time)
TTL event_time + INTERVAL 180 DAY
SETTINGS index_granularity = 8192;

-- Training sample store (pre-computed features for offline training)
CREATE TABLE IF NOT EXISTS shortdrama.training_samples (
    sample_time  DateTime DEFAULT now(),
    user_id      String,
    item_id      String,
    label        UInt8,                    -- 0=negative, 1=positive
    features     Array(Float32),           -- pre-computed feature vector
    split        Enum8('train'=0, 'val'=1, 'test'=2) DEFAULT 'train'
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(sample_time)
ORDER BY (user_id, sample_time)
TTL sample_time + INTERVAL 60 DAY
SETTINGS index_granularity = 8192;
