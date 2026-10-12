-- Initialize PostgreSQL database with required schema
-- This script is run automatically by PostgreSQL during container startup

-- Create required tables for Gold layer export and monitoring

-- ============================================================================
-- EXTENSIONS
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS uuid-ossp;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================================
-- GOLD LAYER TABLES
-- ============================================================================

-- Run history table
CREATE TABLE IF NOT EXISTS run_history (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    status VARCHAR(20) DEFAULT 'running',
    duration_seconds DECIMAL(10, 2),
    user_id VARCHAR(100),
    business_intent TEXT,
    notes TEXT
);

CREATE INDEX idx_run_history_status ON run_history(status);
CREATE INDEX idx_run_history_user_id ON run_history(user_id);
CREATE INDEX idx_run_history_created ON run_history(started_at DESC);

-- Data quality metrics
CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id SERIAL PRIMARY KEY,
    run_id UUID REFERENCES run_history(run_id),
    phase VARCHAR(50),
    agent VARCHAR(50),
    quality_score DECIMAL(5, 2),
    null_count INT,
    duplicate_count INT,
    outlier_count INT,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_quality_run_id ON data_quality_metrics(run_id);
CREATE INDEX idx_quality_phase ON data_quality_metrics(phase);

-- Performance metrics (from performance_monitoring.py)
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    run_id UUID REFERENCES run_history(run_id),
    agent VARCHAR(50),
    phase VARCHAR(50),
    operation VARCHAR(100),
    duration_seconds DECIMAL(10, 3),
    status VARCHAR(20),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_perf_run_id ON performance_metrics(run_id);
CREATE INDEX idx_perf_agent ON performance_metrics(agent);
CREATE INDEX idx_perf_duration ON performance_metrics(duration_seconds DESC);

-- API call costs
CREATE TABLE IF NOT EXISTS api_calls (
    id SERIAL PRIMARY KEY,
    run_id UUID REFERENCES run_history(run_id),
    provider VARCHAR(50),
    model VARCHAR(100),
    input_tokens INT,
    output_tokens INT,
    estimated_cost DECIMAL(10, 6),
    latency_seconds DECIMAL(10, 3),
    status_code INT,
    error_message TEXT,
    called_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_api_run_id ON api_calls(run_id);
CREATE INDEX idx_api_provider ON api_calls(provider);
CREATE INDEX idx_api_cost ON api_calls(estimated_cost DESC);

-- ============================================================================
-- USER MANAGEMENT
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(100) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- User runs
CREATE TABLE IF NOT EXISTS user_runs (
    run_id UUID REFERENCES run_history(run_id),
    user_id VARCHAR(100) REFERENCES users(user_id),
    PRIMARY KEY (run_id, user_id)
);

-- ============================================================================
-- AUDIT & LOGGING
-- ============================================================================

CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    run_id UUID REFERENCES run_history(run_id),
    agent VARCHAR(50),
    action VARCHAR(100),
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_run_id ON audit_log(run_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);

-- Error tracking
CREATE TABLE IF NOT EXISTS error_events (
    id SERIAL PRIMARY KEY,
    run_id UUID REFERENCES run_history(run_id),
    phase VARCHAR(50),
    agent VARCHAR(50),
    error_type VARCHAR(50),
    error_message TEXT,
    stack_trace TEXT,
    recovered BOOLEAN DEFAULT false,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_errors_run_id ON error_events(run_id);
CREATE INDEX idx_errors_type ON error_events(error_type);
CREATE INDEX idx_errors_phase ON error_events(phase);

-- ============================================================================
-- SAMPLE GOLD LAYER DATA TABLE
-- ============================================================================

-- Customer summary (example)
CREATE TABLE IF NOT EXISTS customer_summary (
    customer_id VARCHAR(50) PRIMARY KEY,
    customer_name VARCHAR(255),
    total_transactions INT,
    total_amount DECIMAL(12, 2),
    average_transaction DECIMAL(10, 2),
    last_transaction_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    run_id UUID REFERENCES run_history(run_id)
);

-- ============================================================================
-- VIEWS FOR ANALYSIS
-- ============================================================================

-- Cost summary by provider
CREATE OR REPLACE VIEW cost_summary_by_provider AS
SELECT
    rh.run_id,
    rh.started_at,
    ac.provider,
    COUNT(*) as call_count,
    SUM(ac.input_tokens) as total_input_tokens,
    SUM(ac.output_tokens) as total_output_tokens,
    SUM(ac.estimated_cost) as total_cost
FROM run_history rh
LEFT JOIN api_calls ac ON rh.run_id = ac.run_id
WHERE ac.error_message IS NULL
GROUP BY rh.run_id, rh.started_at, ac.provider;

-- Performance summary by agent
CREATE OR REPLACE VIEW performance_summary_by_agent AS
SELECT
    rh.run_id,
    rh.started_at,
    pm.agent,
    COUNT(*) as operation_count,
    SUM(pm.duration_seconds) as total_duration,
    AVG(pm.duration_seconds) as avg_duration,
    MAX(pm.duration_seconds) as max_duration,
    MIN(pm.duration_seconds) as min_duration
FROM run_history rh
LEFT JOIN performance_metrics pm ON rh.run_id = pm.run_id
GROUP BY rh.run_id, rh.started_at, pm.agent;

-- Error summary
CREATE OR REPLACE VIEW error_summary AS
SELECT
    rh.run_id,
    rh.started_at,
    COUNT(*) as total_errors,
    COUNT(CASE WHEN ee.recovered THEN 1 END) as recovered_errors,
    COUNT(CASE WHEN NOT ee.recovered THEN 1 END) as unrecovered_errors
FROM run_history rh
LEFT JOIN error_events ee ON rh.run_id = ee.run_id
GROUP BY rh.run_id, rh.started_at;
