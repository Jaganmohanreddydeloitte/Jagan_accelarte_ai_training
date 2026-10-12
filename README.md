# 🏅 Agentic Medallion Pipeline (IDAMP)

**Intent-Driven Agentic Medallion Pipeline** — Autonomous AI agents orchestrate your data transformation from raw to analytics-ready in seconds.

> Upload data + ask a question → AI agents profile, transform, validate, and report → You approve at each gate → Done.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [How It Works](#how-it-works)
4. [Project Structure](#project-structure)
5. [Agents](#agents)
6. [Setup & Installation](#setup--installation)
7. [Running the Pipeline](#running-the-pipeline)
8. [Configuration](#configuration)
   - [LLM Configuration](#environment-variables-env)
   - [PostgreSQL Export](#postgresql-export-configuration)
9. [FAQ](#faq)
10. [License](#license)

---

## Overview

### Traditional Data Engineering
Manually transform raw data into analytics-ready tables:
- **Profile** the raw data manually
- **Define** transformation rules by hand
- **Build** ETL pipelines for each layer
- **Monitor** and debug issues
- **Repeat** for each new dataset

❌ Slow, manual, error-prone.

### With IDAMP

1. **Upload** your CSV files
2. **Ask** a business question (intent)
3. **Review & Approve** transformation rules at each gate
4. **Receive** a polished HTML report

✅ Fast, automated, human-approved.

### What Agents Do Automatically

- **Profiler**: Inspects raw data, computes statistics, detects data types and quality issues
- **Bronze Agent**: Maps every column, adds metadata, enforces data types → Raw data layer
- **Silver Agent**: Deduplicates, cleans, normalizes, fills nulls → Trusted data layer
- **Gold Agent**: Creates analytics tables, applies joins, computes metrics → Analytics layer
- **STTM Generator**: Creates transformation rules (Source-to-Target Mappings) using AI
- **Reporter**: Generates interactive HTML reports with visualizations

---

## Architecture

### System Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER (Streamlit)                         │
│                   Upload & Ask Question                         │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                               │
│            (4 Phases, Supervisor Agent Pattern)                 │
└─┬────────────┬────────────┬────────────┬───────────────────────┘
  │            │            │            │
  ▼            ▼            ▼            ▼
┌─────┐   ┌─────┐   ┌─────┐   ┌────────┐
│ P1  │   │ P2  │   │ P3  │   │  P4    │
│Bronze    Silver      Gold    Report
└─────┘   └─────┘   └─────┘   └────────┘
  │         │         │         │
  ▼         ▼         ▼         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Storage (Parquet, CSV, HTML)               │
│    data/bronze_layer/ → data/silver_layer/ → data/gold_layer/  │
└─────────────────────────────────────────────────────────────────┘
```

### Phase Breakdown

| Phase | Agent(s) | Input | Output | Gate | Status |
|-------|----------|-------|--------|------|--------|
| **1** | Profiler, Bronze STTM Gen | CSV files | Bronze STTM rules, profiles | Approve Bronze rules | awaiting_bronze_sttm_approval |
| **2** | Bronze Layer, Silver STTM Gen | Bronze STTM | Bronze Parquet, Silver STTM rules | Approve Silver rules | awaiting_silver_sttm_approval |
| **3** | Silver Layer, Gold STTM Gen | Silver STTM | Silver Parquet, Gold STTM rules | Approve Gold rules | awaiting_gold_sttm_approval |
| **4** | Gold Layer, Reporter | Gold STTM | Gold Parquet, HTML Report | None | completed |

---

## How It Works

### Medallion Architecture

```
                    Business Intent
                          │
                          ▼
         ┌────────────────────────────────┐
         │   Data Landing (Raw CSVs)      │
         └────────────┬───────────────────┘
                      │
                      ▼
         ┌────────────────────────────────┐
         │  BRONZE: Raw Data Ingestion    │
         │  - Type casting                │
         │  - Add metadata                │
         │  - Standardize columns         │
         └────────────┬───────────────────┘
                      │
                      ▼
         ┌────────────────────────────────┐
         │  SILVER: Data Cleansing        │
         │  - Deduplication              │
         │  - Null handling              │
         │  - Text normalization         │
         └────────────┬───────────────────┘
                      │
                      ▼
         ┌────────────────────────────────┐
         │  GOLD: Analytics Tables        │
         │  - Create fact tables          │
         │  - Apply joins                 │
         │  - Compute metrics             │
         └────────────┬───────────────────┘
                      │
                      ▼
         ┌────────────────────────────────┐
         │  REPORT: Executive Summary     │
         │  - Charts & visualizations     │
         │  - Business insights           │
         │  - Interactive HTML            │
         └────────────────────────────────┘
```

### Layer Details

| Layer | Purpose | Input | Output | Key Transforms |
|-------|---------|-------|--------|-----------------|
| **Bronze** | Raw data ingestion | Landing CSV files | Parquet (unchanged structure) | Type casting, metadata columns, standardized names |
| **Silver** | Trusted data | Bronze Parquet | Parquet (refined) | Deduplication, null filling, text normalization, surrogate keys |
| **Gold** | Analytics-ready | Silver Parquet | Parquet (fact tables) | Joins, aggregations, business logic, dimensional tables |

### Agentic Pattern (ReAct)

Each phase uses this loop:

```
1. THINK
   → Agent reads context (profile, rules, data samples)
   → Reasons about transformations needed

2. INSPECT
   → Agent calls inspect_context_tool
   → Examines file shapes, columns, quality

3. PLAN
   → Agent drafts transformation rules
   → Generates STTM (Source-to-Target Mapping)

4. ACT
   → Agent applies rules to data
   → Outputs Parquet files

5. VERIFY
   → Agent logs results to audit trail
   → Traces decisions for transparency
```

---

## Project Structure

```
Accelerate_with_ai_lab/
├── README.md                    # This file
├── .env                         # Environment variables (API keys, secrets)
├── test_import.py               # Quick import sanity check
│
├── core/                        # Infrastructure & utilities
│   ├── __init__.py
│   ├── config.py               # Environment loading, paths, LLM provider detection
│   ├── audit.py                # JSONL audit logging with run_id tracking
│   ├── observability.py        # AgentTrace for detailed reasoning capture
│   ├── state.py                # Pydantic PipelineState TypedDict
│   └── memory.py               # ChromaDB semantic storage & retrieval
│
├── agents/                      # AI agents with LLM backends
│   ├── __init__.py
│   ├── profiler.py             # Inspects data, computes stats (Groq/OpenAI)
│   ├── bronze_agent.py         # Raw data ingestion with type casting
│   ├── silver_agent.py         # Data cleansing (dedup, null fill, normalize)
│   ├── gold_agent.py           # Analytics tables (fact, dimension, join)
│   ├── sttm_generator.py       # Generates transformation rules (LLM)
│   ├── reporter.py             # Creates interactive HTML reports (DuckDB, Plotly)
│   └── orchestrator.py         # Supervisor coordinator (runs phases 1-4)
│
├── app/                         # User interface
│   ├── __init__.py
│   └── streamlit_app.py        # Web UI for upload, review, approve, report
│
├── tests/                       # 93 comprehensive test cases
│   ├── conftest.py             # Shared pytest fixtures
│   ├── test_audit.py           # AuditLogger tests (10 tests)
│   ├── test_bronze.py          # Bronze layer tests (12 tests)
│   ├── test_silver.py          # Silver layer tests (13 tests)
│   ├── test_gold.py            # Gold layer tests (13 tests)
│   ├── test_profiler.py        # Profiler tests (12 tests)
│   ├── test_reporter.py        # Reporter tests (14 tests)
│   ├── test_sttm.py            # STTM generator tests (19 tests)
│   └── README.md               # Testing guide & CI/CD integration
│
├── data/                        # Data storage (created automatically)
│   ├── landing/                # Uploaded CSV files
│   ├── profiles/               # JSON profile outputs
│   ├── bronze_layer/           # Raw data (Parquet)
│   ├── silver_layer/           # Cleaned data (Parquet)
│   ├── gold_layer/             # Analytics tables (Parquet)
│   ├── sttm/                   # Transformation rules (CSV)
│   ├── reports/                # HTML reports
│   ├── traces/                 # Agent reasoning traces (JSON)
│   └── audit_logs/             # Audit trail (JSONL)
│
├── pytest.ini                   # Pytest configuration
└── requirements.txt             # Python dependencies
```

---

## Agents

### 1. Profiler Agent
**Purpose**: Inspect raw data and generate semantic profile  
**Tools**:
- `inspect_files()` — Read CSV files, compute row/column counts
- `compute_stats()` — Statistics (min, max, mean, mode, null %)
- `save_profile()` — Output JSON profile with semantic meanings

**Output**: `data/profiles/{run_id}.json`

---

### 2. Bronze Agent
**Purpose**: Ingest raw data with metadata and type casting  
**Tools**:
- `load_bronze_sttm()` — Load transformation rules
- `apply_bronze_rules()` — Map columns, add _load_timestamp, _source_file
- `save_bronze_output()` — Write Parquet files

**Output**: `data/bronze_layer/{filename}.parquet`

---

### 3. Silver Agent
**Purpose**: Cleanse and standardize data  
**Tools**:
- `load_silver_sttm()` — Load cleansing rules
- `apply_silver_rules()` — Dedup, fill nulls, normalize text, inject surrogate keys
- `save_silver_output()` — Write Parquet files

**Output**: `data/silver_layer/{filename}.parquet`

---

### 4. Gold Agent
**Purpose**: Create analytics tables and fact tables  
**Tools**:
- `load_gold_sttm()` — Load table definitions
- `apply_gold_rules()` — Create fact/dimension tables, apply joins
- `save_gold_output()` — Write Parquet files

**Output**: `data/gold_layer/{table_name}.parquet`

---

### 5. STTM Generator Agent
**Purpose**: Generate transformation rules using AI  
**Workflow**:
1. Inspect context (data profile, previous STTM rules)
2. Call appropriate generation tool (Bronze/Silver/Gold)
3. Extract and validate JSON array of transformation rows
4. Save as CSV STTM file for human review

**Output**: `data/sttm/{layer}_sttm_{run_id[:8]}.csv`

---

### 6. Reporter Agent
**Purpose**: Generate executive reports with visualizations  
**Tools**:
- `load_gold_tables()` — Inspect Gold Parquet files, register with DuckDB
- `execute_query()` — Run SQL on Gold tables
- `generate_chart()` — Create Plotly visualizations (bar, pie, line, scatter)
- `submit_analysis()` — Compile charts into HTML report

**Output**: `data/reports/report_{run_id[:8]}.html`

---

### 7. Orchestrator (Supervisor Agent)
**Purpose**: Coordinate all agents through 4 phases  
**Functions**:
- `run_until_bronze_sttm()` — Phase 1: Profile → Bronze STTM
- `run_bronze_to_silver_sttm()` — Phase 2: Bronze → Silver STTM
- `run_silver_to_gold_sttm()` — Phase 3: Silver → Gold STTM
- `run_gold_and_report()` — Phase 4: Gold → Report

**Pattern**: Supervisor agent chains tools via scratchpad, logs audit trail at each step.

---

## Setup & Installation

### Prerequisites

- **Python 3.11+**
- **pip** (Python package manager)
- **API Keys**:
  - [Groq API](https://console.groq.com) (recommended, fastest)
  - or [OpenAI API](https://platform.openai.com/api-keys)
  - or [Google Gemini API](https://ai.google.dev/tutorials/python_quickstart)

### Installation Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Accelerate_with_ai_lab
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Verify imports**
   ```bash
   python test_import.py
   ```
   Expected output: `SUCCESS! All core imports worked.`

---

## Running the Pipeline

### Start the Streamlit App

```bash
streamlit run app/streamlit_app.py
```

**URL**: http://localhost:8501

### Workflow in Streamlit

1. **Phase 1: Upload & Intent**
   - Upload CSV files
   - Enter business question
   - Click "🚀 Start Workflow"
   - Agent profiles data and generates Bronze STTM rules

2. **Phase 2: Bronze Review**
   - Inspect Bronze transformation rules
   - Select rows to approve
   - Click "✅ Approve & Continue"
   - Agent applies rules and generates Silver STTM rules

3. **Phase 3: Silver Review**
   - Inspect Silver transformation rules
   - Approve selected rows
   - Agent applies rules and generates Gold STTM rules

4. **Phase 4: Gold Review**
   - Inspect Gold transformation rules
   - Approve selected rows
   - Agent applies rules and generates report

5. **Phase 5: Report**
   - View interactive HTML report
   - Download or start new analysis

---

## Configuration

### Environment Variables (`.env`)

```bash
# LLM Provider (auto-detect: groq > openai > gemini)
LLM_PROVIDER=groq

# Groq (recommended)
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=llama-3.3-70b-versatile

# OpenAI (fallback)
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini

# Google Gemini
GOOGLE_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash

# Embeddings
EMBEDDING_MODEL=models/text-embedding-004

# GitHub Models (advanced)
GITHUB_TOKEN=your_github_token
GITHUB_BASE_URL=https://models.inference.ai.azure.com
GITHUB_MODEL=openai/gpt-4.1-mini
```

### PostgreSQL Export Configuration

Export your Gold layer analytics tables to PostgreSQL database (optional):

```bash
# Enable PostgreSQL export
ENABLE_POSTGRES_EXPORT=true

# Connection string
DATABASE_URL=postgresql://username:password@hostname:5432/database_name

# Alternative: Use individual values
# POSTGRES_USER=postgres
# POSTGRES_PASSWORD=your-password
# POSTGRES_HOST=localhost
# POSTGRES_PORT=5432
# POSTGRES_DATABASE=idamp_analytics

# Schema and options
POSTGRES_SCHEMA=analytics
POSTGRES_AUTO_CREATE_TABLES=true
POSTGRES_DROP_EXISTING_TABLES=false
```

**Getting Started with PostgreSQL:**

1. **Local Development (SQLite alternative):**
   ```bash
   # Install PostgreSQL locally
   brew install postgresql  # macOS
   sudo apt-get install postgresql  # Linux
   
   # Create database
   psql -U postgres -c "CREATE DATABASE idamp_analytics;"
   psql -U postgres -c "CREATE USER idamp_user WITH PASSWORD 'password';"
   
   # Set DATABASE_URL in .env
   DATABASE_URL=postgresql://idamp_user:password@localhost:5432/idamp_analytics
   ```

2. **Cloud Providers:**
   - **AWS RDS**: Create managed PostgreSQL instance, use endpoint in DATABASE_URL
   - **Google Cloud SQL**: Use Cloud SQL Proxy for secure connection
   - **Azure Database for PostgreSQL**: Create via Azure portal
   - **Heroku PostgreSQL**: Automatically provided as DATABASE_URL

3. **Verify Connection:**
   ```bash
   psql -U idamp_user -d idamp_analytics -h localhost
   SELECT * FROM analytics.customers LIMIT 5;
   ```

**Security Notes:**
- Store database passwords in `.env` only (never in code)
- Use SSL/TLS for remote connections: `?sslmode=require`
- Create restricted database user (not superuser)
- Enable audit logging on PostgreSQL server
- Rotate passwords every 90 days

See [POSTGRES_EXPORT_GUIDE.md](POSTGRES_EXPORT_GUIDE.md) for complete setup instructions, troubleshooting, and advanced configuration.

### Project Configuration

Edit `core/config.py` to customize:
- Directory paths (`BASE_DIR`, `DATA_DIR`, `BRONZE_DIR`, etc.)
- LLM provider selection
- Default models

---

## FAQ

### Q: How do I upload data?
**A**: In the Streamlit app, go to Phase 1 and use the file uploader. Supports CSV files.

### Q: What data quality issues does the Profiler detect?
**A**: Row/column counts, missing values, data types, numeric ranges, text patterns, duplicates.

### Q: Can I edit transformation rules?
**A**: Yes! Each phase shows STTM rules in a data editor. Check/uncheck rows to approve selectively.

### Q: How are transformation rules generated?
**A**: An LLM agent (Groq/OpenAI/Gemini) reads the data profile and context, then generates rules as JSON arrays of transformation specifications.

### Q: What happens if an agent fails?
**A**: The pipeline catches the error, logs it to the audit trail, and shows an error message in Streamlit. You can restart from that phase.

### Q: Can I use this with a different LLM?
**A**: Yes. Set `LLM_PROVIDER` in `.env` to `groq`, `openai`, or `gemini`. The orchestrator auto-detects available API keys.

### Q: What does the audit trail track?
**A**: Every agent action: phase start/complete/fail, transformation applied, rows affected, timestamps, errors.

### Q: How do I inspect the HTML report offline?
**A**: Download it from Phase 5, then open in any web browser. It's self-contained (Plotly CDN).

### Q: Can I run this in production?
**A**: Yes, but consider:
- Using environment-specific `.env` files
- Running agents in containers (Docker)
- Storing audit logs in a centralized database
- Adding monitoring/alerting on agent failures
- Using an orchestration tool (Airflow, Prefect, Dagster)

### Q: How do I run tests?
**A**: 
```bash
# All tests
pytest tests/

# Specific test file
pytest tests/test_bronze.py -v

# With coverage
pytest tests/ --cov=. --cov-report=html
```

### Q: Can I export Gold data to PostgreSQL?
**A**: Yes! Set `ENABLE_POSTGRES_EXPORT=true` and configure `DATABASE_URL` in `.env`. Gold layer Parquet files are automatically exported to PostgreSQL tables after processing. Tables are created automatically from the Parquet schema. See [POSTGRES_EXPORT_GUIDE.md](POSTGRES_EXPORT_GUIDE.md) for setup.

### Q: What PostgreSQL providers are supported?
**A**: Any PostgreSQL-compatible database: local PostgreSQL, AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL, Heroku Postgres, or self-hosted. Configure via connection string in `DATABASE_URL`.

### Q: What if PostgreSQL export fails?
**A**: The pipeline continues and logs the error to the audit trail. PostgreSQL export is optional — Parquet files are always saved regardless. Check audit logs in `audit_logs/` for detailed error messages.

### Q: How do I query the exported Gold tables?
**A**: Connect to PostgreSQL and query like any other database:
```sql
-- List tables in analytics schema
SELECT table_name FROM information_schema.tables WHERE table_schema = 'analytics';

-- Query customers table
SELECT COUNT(*) FROM analytics.customers;

-- Join tables
SELECT c.customer_id, o.order_id FROM analytics.customers c
  JOIN analytics.orders o ON c.customer_id = o.customer_id;
```

### Q: What's the difference between Parquet and PostgreSQL export?
**A**: Parquet files are columnar, compressed, and immutable (good for storage/archive). PostgreSQL provides SQL querying, transactions, and real-time access (good for analytics/BI tools). IDAMP exports to both — use Parquet for backups, PostgreSQL for live queries.

### Q: Can I schedule the pipeline to run automatically?
**A**: Yes, use `agents/cli.py` with cron (Linux/Mac) or Task Scheduler (Windows). See [SCHEDULED_EXECUTION_GUIDE.md](SCHEDULED_EXECUTION_GUIDE.md) for examples. Scheduled runs will export to PostgreSQL if enabled.

### Q: What's the difference between phases?
**A**: 
- **Phase 1**: Profile data, generate Bronze rules
- **Phase 2**: Load Bronze data, generate Silver rules
- **Phase 3**: Load Silver data, generate Gold rules
- **Phase 4**: Load Gold data, generate report

Each phase depends on the previous one's output.

---

## Architecture Highlights

### Why Agentic?
- **Reasoning**: Agents "think through" transformations using ReAct pattern
- **Flexibility**: Rules adapt to data shape and quality issues
- **Transparency**: Every decision logged in audit trail
- **Approval Gates**: Humans review and approve before each layer

### Why Medallion?
- **Bronze**: Exact copy of raw data + metadata (100% data)
- **Silver**: Cleaned, deduplicated, standardized (90-98% data)
- **Gold**: Business-ready analytics tables (80-95% data)
- **Traceability**: Each row can be traced back to source

### Why Medallion + Agentic?
Medallion layers ensure data quality at each stage. Agentic orchestration automates the transformation logic while keeping humans in the loop via approval gates.

---

## Performance Tips

- **Large datasets (>1M rows)**: Use Groq (faster, cheaper) or run agents in parallel
- **Many files**: Batch files into phases; agent processes one file at a time
- **Slow reports**: Reduce Gold table row count before report generation
- **Memory issues**: Process files individually instead of all at once

---

## Troubleshooting

**Import Error: `ModuleNotFoundError`**
- Run `python test_import.py` to diagnose
- Ensure `core/`, `agents/`, `app/` folders exist
- Verify Python 3.11+ installed

**API Key Error: `Unauthorized`**
- Check `.env` file has correct API key
- Verify API key is still valid (not expired/revoked)
- Ensure `LLM_PROVIDER` matches available key

**Streamlit Error: `Connection refused`**
- Ensure Streamlit app is running: `streamlit run app/streamlit_app.py`
- Check port 8501 not in use: `netstat -an | grep 8501`

**Agent Timeout**
- Increase timeout in orchestrator (default 300s)
- Use Groq (faster) instead of OpenAI
- Reduce data size or enable sampling

---

## Contributing

Contributions welcome! 

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make changes and add tests (`tests/`)
4. Run test suite: `pytest tests/`
5. Push and create a Pull Request

---

## License

MIT License — see LICENSE file for details.

---

**Ready to transform data with AI?** 

```bash
streamlit run app/streamlit_app.py
```

🚀 Happy transforming!
