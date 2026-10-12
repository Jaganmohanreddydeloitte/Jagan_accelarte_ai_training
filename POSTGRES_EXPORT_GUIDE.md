# PostgreSQL Export for Gold Layer

Complete guide to export your Gold layer analytics tables to PostgreSQL database with automatic table creation.

---

## 1. Packages to Install

### Add to requirements.txt:

```
psycopg2-binary==2.9.9  # PostgreSQL adapter for Python
sqlalchemy==2.0.23      # SQL toolkit and ORM
pandas==2.1.4           # Already have this
pyarrow==14.0.1         # Already have this (Parquet reader)
```

**Note:** You may already have pandas and pyarrow. Just add the new ones.

### Install:

```bash
pip install psycopg2-binary sqlalchemy
```

---

## 2. PostgreSQL Configuration

### Add to .env file:

```bash
# ─── PostgreSQL Configuration ───────────────────────────────────────
# IMPORTANT: These are SENSITIVE. Never commit .env to git!

# Enable/Disable PostgreSQL Export
ENABLE_POSTGRES_EXPORT=true

# PostgreSQL Connection String
# Format: postgresql://username:password@hostname:port/database_name
# Default port: 5432

# Option 1: Direct connection string
DATABASE_URL=postgresql://postgres:password@localhost:5432/idamp_analytics

# Option 2: Individual components (alternative)
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-secure-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=idamp_analytics

# PostgreSQL Schema (default: public)
POSTGRES_SCHEMA=analytics

# Optional: SSL Mode (disable, allow, prefer, require)
# POSTGRES_SSL_MODE=prefer

# Auto-create tables if they don't exist
POSTGRES_AUTO_CREATE_TABLES=true

# Drop existing tables before recreating (for testing only!)
POSTGRES_DROP_EXISTING_TABLES=false
```

### Create .env.example template:

```bash
# PostgreSQL Configuration (EXAMPLE - fill in your actual values)
ENABLE_POSTGRES_EXPORT=true
DATABASE_URL=postgresql://username:password@hostname:5432/database_name
POSTGRES_SCHEMA=analytics
POSTGRES_AUTO_CREATE_TABLES=true
POSTGRES_DROP_EXISTING_TABLES=false
```

---

## 3. PostgreSQL Connection Module

### New File: core/postgres_exporter.py

```python
"""PostgreSQL export for Gold layer analytics tables."""

import os
from pathlib import Path
from typing import Optional, Dict, List
import logging

import pandas as pd
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Boolean,
    inspect,
    text,
)
from sqlalchemy.types import (
    VARCHAR,
    BIGINT,
    NUMERIC,
    TIMESTAMP,
    BOOLEAN,
)

from core.audit import AuditLogger


# ─── Configuration ──────────────────────────────────────────────────────────

ENABLE_POSTGRES = os.getenv("ENABLE_POSTGRES_EXPORT", "false").lower() == "true"

# Option 1: Direct DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "")

# Option 2: Individual components
if not DATABASE_URL:
    POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DATABASE = os.getenv("POSTGRES_DATABASE", "")
    
    if POSTGRES_DATABASE:
        DATABASE_URL = (
            f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
            f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
        )

POSTGRES_SCHEMA = os.getenv("POSTGRES_SCHEMA", "public")
AUTO_CREATE_TABLES = os.getenv("POSTGRES_AUTO_CREATE_TABLES", "true").lower() == "true"
DROP_EXISTING = os.getenv("POSTGRES_DROP_EXISTING_TABLES", "false").lower() == "true"


# ─── PostgreSQL Exporter ────────────────────────────────────────────────────

class PostgreSQLExporter:
    """Export Gold layer Parquet files to PostgreSQL."""
    
    def __init__(self, run_id: str):
        """Initialize PostgreSQL exporter."""
        self.run_id = run_id
        self.logger = AuditLogger(run_id)
        self.engine = None
        self.connection_string = DATABASE_URL
    
    def connect(self) -> bool:
        """
        Establish connection to PostgreSQL.
        
        Returns:
            True if connection successful, False otherwise
        """
        if not ENABLE_POSTGRES:
            self.logger.log("postgres_exporter", "postgres_disabled")
            return False
        
        if not DATABASE_URL:
            self.logger.log(
                "postgres_exporter",
                "postgres_error",
                error="DATABASE_URL not configured in .env",
            )
            print("❌ PostgreSQL not configured. Set DATABASE_URL in .env")
            return False
        
        try:
            # Create engine with connection pooling
            self.engine = create_engine(
                DATABASE_URL,
                echo=False,  # Set to True for SQL debugging
                pool_pre_ping=True,  # Verify connections before using
                pool_size=10,
                max_overflow=20,
            )
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            self.logger.log("postgres_exporter", "connect_success")
            print("✅ Connected to PostgreSQL")
            return True
        
        except Exception as e:
            error_msg = f"PostgreSQL connection failed: {e}"
            self.logger.log(
                "postgres_exporter",
                "connect_failed",
                error=str(e),
            )
            print(f"❌ {error_msg}")
            return False
    
    def _get_sql_type(self, pandas_dtype: str) -> object:
        """Map pandas dtype to SQLAlchemy type."""
        dtype_str = str(pandas_dtype).lower()
        
        if "int" in dtype_str:
            return BIGINT()
        elif "float" in dtype_str or "double" in dtype_str:
            return NUMERIC(precision=18, scale=6)
        elif "bool" in dtype_str:
            return BOOLEAN()
        elif "datetime" in dtype_str or "timestamp" in dtype_str:
            return TIMESTAMP(timezone=True)
        else:
            return VARCHAR(255)
    
    def _create_table_from_parquet(
        self,
        table_name: str,
        parquet_path: str,
    ) -> bool:
        """
        Create PostgreSQL table from Parquet file schema.
        
        Args:
            table_name: Name of the table to create
            parquet_path: Path to Parquet file
        
        Returns:
            True if table created successfully
        """
        try:
            # Read Parquet file to get schema
            df = pd.read_parquet(parquet_path)
            
            if df.empty:
                self.logger.log(
                    "postgres_exporter",
                    "table_creation_skipped",
                    reason="Parquet file is empty",
                    table_name=table_name,
                )
                return False
            
            # Drop existing table if configured
            if DROP_EXISTING:
                with self.engine.connect() as conn:
                    conn.execute(text(f'DROP TABLE IF EXISTS "{POSTGRES_SCHEMA}"."{table_name}" CASCADE'))
                    conn.commit()
            
            # Create columns from DataFrame schema
            columns = []
            for col_name, dtype in df.dtypes.items():
                sql_type = self._get_sql_type(str(dtype))
                columns.append(Column(col_name, sql_type, nullable=True))
            
            # Add surrogate key if not present
            if "_surrogate_key" not in df.columns:
                columns.insert(0, Column("_surrogate_key", VARCHAR(36), nullable=False, primary_key=True))
            
            # Create table using SQLAlchemy
            table = Table(
                table_name,
                MetaData(schema=POSTGRES_SCHEMA),
                *columns,
            )
            
            table.create(self.engine, checkfirst=True)
            
            self.logger.log(
                "postgres_exporter",
                "table_created",
                table_name=table_name,
                column_count=len(columns),
            )
            print(f"✅ Created table: {POSTGRES_SCHEMA}.{table_name}")
            
            return True
        
        except Exception as e:
            self.logger.log(
                "postgres_exporter",
                "table_creation_failed",
                table_name=table_name,
                error=str(e),
            )
            print(f"❌ Failed to create table {table_name}: {e}")
            return False
    
    def export_parquet_to_table(
        self,
        table_name: str,
        parquet_path: str,
        truncate_first: bool = True,
    ) -> bool:
        """
        Export Parquet file data to PostgreSQL table.
        
        Args:
            table_name: Name of the target table
            parquet_path: Path to Parquet file
            truncate_first: Truncate table before inserting new data
        
        Returns:
            True if export successful
        """
        if not self.engine:
            return False
        
        try:
            # Read Parquet file
            df = pd.read_parquet(parquet_path)
            
            if df.empty:
                self.logger.log(
                    "postgres_exporter",
                    "export_skipped",
                    reason="Parquet file is empty",
                    table_name=table_name,
                )
                print(f"⚠️  Skipping {table_name} - no data in Parquet file")
                return False
            
            # Truncate table if configured
            if truncate_first:
                with self.engine.connect() as conn:
                    conn.execute(text(f'TRUNCATE TABLE "{POSTGRES_SCHEMA}"."{table_name}" CASCADE'))
                    conn.commit()
            
            # Insert data using SQLAlchemy's to_sql
            # This automatically creates table if it doesn't exist
            row_count = df.to_sql(
                table_name,
                self.engine,
                schema=POSTGRES_SCHEMA,
                if_exists="append",  # Append to existing table
                index=False,
                chunksize=1000,  # Insert in batches of 1000
                method="multi",  # Use executemany for faster inserts
            )
            
            self.logger.log(
                "postgres_exporter",
                "export_success",
                table_name=table_name,
                row_count=len(df),
            )
            print(f"✅ Exported {len(df)} rows to {POSTGRES_SCHEMA}.{table_name}")
            
            return True
        
        except Exception as e:
            self.logger.log(
                "postgres_exporter",
                "export_failed",
                table_name=table_name,
                error=str(e),
            )
            print(f"❌ Export failed for {table_name}: {e}")
            return False
    
    def export_gold_layer(self, gold_output_paths: list[str]) -> Dict[str, bool]:
        """
        Export all Gold layer Parquet files to PostgreSQL.
        
        Args:
            gold_output_paths: List of Parquet file paths
        
        Returns:
            Dict mapping table_name -> success (True/False)
        """
        results = {}
        
        if not self.connect():
            return {Path(p).stem: False for p in gold_output_paths}
        
        for parquet_path in gold_output_paths:
            # Extract table name from filename (without .parquet)
            table_name = Path(parquet_path).stem
            
            # Create table first
            self._create_table_from_parquet(table_name, parquet_path)
            
            # Export data
            success = self.export_parquet_to_table(table_name, parquet_path)
            results[table_name] = success
        
        self._log_export_summary(results)
        return results
    
    def _log_export_summary(self, results: Dict[str, bool]) -> None:
        """Log summary of export results."""
        successful = sum(1 for v in results.values() if v)
        total = len(results)
        
        summary = f"PostgreSQL export: {successful}/{total} tables successful"
        self.logger.log("postgres_exporter", "export_summary", summary=summary)
        
        print("\n" + "="*70)
        print(f"PostgreSQL Export Summary: {successful}/{total} tables")
        print("="*70)
        for table_name, success in results.items():
            status = "✅ SUCCESS" if success else "❌ FAILED"
            print(f"{status} - {table_name}")
        print("="*70 + "\n")
    
    def close(self) -> None:
        """Close database connection."""
        if self.engine:
            self.engine.dispose()
            self.logger.log("postgres_exporter", "connection_closed")


# ─── Convenience Function ───────────────────────────────────────────────────

def export_gold_to_postgres(run_id: str, gold_output_paths: list[str]) -> Dict[str, bool]:
    """
    Export Gold layer to PostgreSQL.
    
    Args:
        run_id: Pipeline run ID
        gold_output_paths: List of Parquet file paths
    
    Returns:
        Dict mapping table_name -> success status
    """
    exporter = PostgreSQLExporter(run_id)
    try:
        return exporter.export_gold_layer(gold_output_paths)
    finally:
        exporter.close()
```

---

## 4. Modify Gold Agent to Export

### File: agents/gold_agent.py

Find the `execute_gold()` function. At the very end, after all Parquet files are written:

### Current Code (end of function):

```python
def execute_gold(
    silver_output_paths: list[str],
    silver_sttm_path: str,
    gold_sttm_path: str,
    run_id: str,
) -> list[str]:
    """Apply Gold layer transformations and return output paths."""
    trace = AgentTrace("gold_agent", run_id)
    logger = AuditLogger(run_id)
    
    try:
        # ... gold processing code ...
        
        # Save output files
        output_paths = []
        for table_name, table_data in gold_tables.items():
            output_path = GOLD_DIR / f"{table_name}.parquet"
            table_data.to_parquet(output_path)
            output_paths.append(str(output_path))
        
        trace.set_output(gold_output_paths=output_paths)
        trace.complete(status="success")
        return output_paths
    
    except Exception as e:
        trace.fail(str(e))
        raise
```

### New Code (add this before return):

```python
def execute_gold(
    silver_output_paths: list[str],
    silver_sttm_path: str,
    gold_sttm_path: str,
    run_id: str,
) -> list[str]:
    """Apply Gold layer transformations and return output paths."""
    trace = AgentTrace("gold_agent", run_id)
    logger = AuditLogger(run_id)
    
    try:
        # ... gold processing code ...
        
        # Save output files
        output_paths = []
        for table_name, table_data in gold_tables.items():
            output_path = GOLD_DIR / f"{table_name}.parquet"
            table_data.to_parquet(output_path)
            output_paths.append(str(output_path))
        
        # ────────────────────────────────────────────────────────────────
        # NEW: Export to PostgreSQL
        # ────────────────────────────────────────────────────────────────
        logger.log("gold_agent", "postgres_export_start", table_count=len(output_paths))
        
        try:
            from core.postgres_exporter import export_gold_to_postgres
            
            export_results = export_gold_to_postgres(run_id, output_paths)
            
            # Log results
            successful = sum(1 for v in export_results.values() if v)
            logger.log(
                "gold_agent",
                "postgres_export_complete",
                successful=successful,
                total=len(export_results),
            )
        
        except Exception as postgres_error:
            # Log but don't fail - PostgreSQL is optional
            logger.log(
                "gold_agent",
                "postgres_export_error",
                error=str(postgres_error),
            )
            print(f"⚠️  PostgreSQL export failed (non-fatal): {postgres_error}")
        
        trace.set_output(gold_output_paths=output_paths)
        trace.complete(status="success")
        return output_paths
    
    except Exception as e:
        trace.fail(str(e))
        raise
```

---

## 5. Database Connection String Formats

### PostgreSQL Connection Strings

```bash
# Basic (localhost)
postgresql://postgres:password@localhost:5432/database_name

# With username/password
postgresql://myuser:mypassword@localhost:5432/my_database

# Remote server
postgresql://user:pass@db.company.com:5432/analytics

# With SSL (recommended for production)
postgresql://user:pass@db.company.com:5432/analytics?sslmode=require

# With port forwarding (SSH tunnel)
postgresql://user:pass@127.0.0.1:5433/database_name
# (assumes: ssh -L 5433:db.company.com:5432 user@bastion)
```

### Connection String Components

```
postgresql://username:password@hostname:port/database_name
              ^^^^^^^^  ^^^^^^^^  ^^^^^^^^  ^^^^  ^^^^^^^^^^^^^
              user      password  host      port  database
```

---

## 6. PostgreSQL Setup Instructions

### Option 1: Local PostgreSQL (Development)

**Install PostgreSQL:**

```bash
# macOS (using Homebrew)
brew install postgresql
brew services start postgresql

# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib
sudo systemctl start postgresql

# Windows
# Download from https://www.postgresql.org/download/windows/
# Run installer and remember the password
```

**Create database:**

```bash
# Connect to PostgreSQL
psql -U postgres

# Create database and user
CREATE DATABASE idamp_analytics;
CREATE USER idamp_user WITH PASSWORD 'your-secure-password';
ALTER ROLE idamp_user SET client_encoding TO 'utf8';
ALTER ROLE idamp_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE idamp_user SET default_transaction_deferrable TO on;
GRANT ALL PRIVILEGES ON DATABASE idamp_analytics TO idamp_user;

# Exit
\q
```

**Test connection:**

```bash
psql -U idamp_user -d idamp_analytics -h localhost -W
# Enter password when prompted
# Type \q to exit
```

### Option 2: Cloud PostgreSQL (Production)

**AWS RDS:**
```
postgresql://username:password@mydb.123456789.us-east-1.rds.amazonaws.com:5432/mydb
```

**Google Cloud SQL:**
```
postgresql://username:password@10.0.0.2:5432/mydb
# (Use Cloud SQL Proxy for secure connection)
```

**Azure Database for PostgreSQL:**
```
postgresql://username@servername:password@servername.postgres.database.azure.com:5432/mydb
```

**Heroku PostgreSQL:**
```
# Automatically set as DATABASE_URL environment variable
postgresql://user:password@ec2-12-34-567-890.compute-1.amazonaws.com:5432/database_name
```

---

## 7. Security Considerations

### ⚠️ CRITICAL Security Checklist

- [ ] **Never hardcode passwords** — Use .env file (excluded from git)
- [ ] **Never commit .env** — Already in .gitignore, verify
- [ ] **Use app-specific passwords** — Don't share your personal DB password
- [ ] **Enable SSL/TLS** — Use `?sslmode=require` in connection string
- [ ] **Use least privilege** — Create database user with minimal required permissions
- [ ] **Rotate passwords regularly** — Change database password every 90 days
- [ ] **Use VPC/firewall** — Restrict database access to your app only
- [ ] **Enable audit logging** — PostgreSQL logs should track who modified what
- [ ] **Backup regularly** — Daily automated backups to secure location
- [ ] **Monitor for unusual activity** — Set up alerts on connection failures

### PostgreSQL User Permissions (Principle of Least Privilege)

```bash
# Create restricted user (production)
CREATE USER idamp_gold_user WITH PASSWORD 'strong-password-here';

# Grant only necessary permissions
GRANT CONNECT ON DATABASE idamp_analytics TO idamp_gold_user;
GRANT USAGE ON SCHEMA analytics TO idamp_gold_user;
GRANT CREATE ON SCHEMA analytics TO idamp_gold_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA analytics TO idamp_gold_user;

# Don't grant superuser or createdb permissions
```

### SSL/TLS Configuration

```bash
# In .env
DATABASE_URL=postgresql://user:pass@db.company.com/db?sslmode=require

# Connection string parameters:
# sslmode options:
#   disable   - No SSL (INSECURE)
#   allow     - SSL if server supports it
#   prefer    - Prefer SSL (default)
#   require   - Require SSL
#   verify-ca - Require SSL + verify CA certificate
#   verify-full - Require SSL + verify CA + hostname
```

---

## 8. Testing PostgreSQL Export

### Test 1: Connection Test

```python
from core.postgres_exporter import PostgreSQLExporter

exporter = PostgreSQLExporter("test-run")
if exporter.connect():
    print("✅ Connection successful")
else:
    print("❌ Connection failed")
exporter.close()
```

### Test 2: Export Single Table

```bash
python -c "
import pandas as pd
from core.postgres_exporter import PostgreSQLExporter

# Create test Parquet
df = pd.DataFrame({
    'id': [1, 2, 3],
    'name': ['Alice', 'Bob', 'Charlie'],
    'amount': [100.0, 200.0, 300.0],
})
df.to_parquet('test_table.parquet', index=False)

# Export
exporter = PostgreSQLExporter('test-run-001')
exporter.export_parquet_to_table('test_table', 'test_table.parquet')
exporter.close()
"
```

### Test 3: Query PostgreSQL

```bash
# Connect to database
psql -U idamp_user -d idamp_analytics -h localhost

# List tables
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'analytics';

# Count rows in a table
SELECT COUNT(*) FROM analytics."customers";

# View first 5 rows
SELECT * FROM analytics."customers" LIMIT 5;

# Exit
\q
```

### Test 4: Full Pipeline Export

1. Run IDAMP pipeline to completion
2. Check PostgreSQL tables were created:
   ```bash
   psql -U idamp_user -d idamp_analytics -c "SELECT COUNT(*) FROM analytics.\"customers\";"
   ```
3. Verify row counts match Parquet files

---

## 9. .env Configuration Examples

### Development (Local PostgreSQL)

```bash
ENABLE_POSTGRES_EXPORT=true
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=idamp_analytics
POSTGRES_SCHEMA=analytics
POSTGRES_AUTO_CREATE_TABLES=true
POSTGRES_DROP_EXISTING_TABLES=false
```

### Production (AWS RDS)

```bash
ENABLE_POSTGRES_EXPORT=true
DATABASE_URL=postgresql://idamp_user:your-secure-password@mydb.123456789.us-east-1.rds.amazonaws.com:5432/idamp_analytics?sslmode=require
POSTGRES_SCHEMA=analytics
POSTGRES_AUTO_CREATE_TABLES=true
POSTGRES_DROP_EXISTING_TABLES=false
```

### Production (Cloud SQL with Proxy)

```bash
ENABLE_POSTGRES_EXPORT=true
DATABASE_URL=postgresql://idamp_user:password@127.0.0.1:5432/idamp_analytics?sslmode=require
# (Assumes Cloud SQL Proxy running: cloud_sql_proxy -instances=project:region:instance=tcp:5432)
POSTGRES_SCHEMA=analytics
POSTGRES_AUTO_CREATE_TABLES=true
POSTGRES_DROP_EXISTING_TABLES=false
```

### Disabled (Testing without Database)

```bash
ENABLE_POSTGRES_EXPORT=false
# Other keys can be empty
```

---

## 10. Troubleshooting

| Error | Cause | Solution |
|-------|-------|----------|
| `PostgreSQL connection failed` | Wrong host/port/password | Verify DATABASE_URL and .env settings |
| `FATAL: role "user" does not exist` | User not created | Create user with: CREATE USER ... |
| `FATAL: database "db" does not exist` | Database not created | Create with: CREATE DATABASE ... |
| `SSL connection error` | SSL mode mismatch | Try sslmode=allow or check server cert |
| `permission denied for schema` | User lacks permissions | Grant permissions to user |
| `timeout connecting to server` | Firewall blocking | Check firewall rules, allow port 5432 |
| `ERROR: type "VARCHAR" does not exist` | Schema/extension issue | Usually auto-resolved on retry |

---

## 11. Monitoring & Maintenance

### Query Database Size

```sql
SELECT 
    datname as database,
    pg_size_pretty(pg_database_size(datname)) as size
FROM pg_database
WHERE datname = 'idamp_analytics';
```

### Find Slow Queries

```sql
SELECT query, calls, mean_time, total_time
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

### Table Row Counts

```sql
SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE schemaname = 'analytics'
ORDER BY n_live_tup DESC;
```

### Create Backup

```bash
pg_dump -U idamp_user -d idamp_analytics -h localhost > backup_$(date +%Y%m%d).sql

# Restore from backup
psql -U idamp_user -d idamp_analytics -h localhost < backup_20261007.sql
```

---

## 12. Architecture Diagram

```
Gold Agent (Parquet files)
        │
        ├─→ data/gold_layer/customers.parquet
        ├─→ data/gold_layer/orders.parquet
        └─→ data/gold_layer/products.parquet
        
        ↓ PostgreSQL Export
        
PostgreSQL Database
        │
        ├─→ analytics.customers (table)
        ├─→ analytics.orders (table)
        └─→ analytics.products (table)
        
        ↓ Access via SQL
        
Analytics Queries
        │
        ├─→ SELECT * FROM analytics.customers WHERE region = 'USA'
        ├─→ SELECT COUNT(*) FROM analytics.orders
        └─→ JOIN operations across tables
```

---

## 13. Summary of Changes

| File | Type | Change |
|------|------|--------|
| `core/postgres_exporter.py` | NEW | PostgreSQL export module (380 lines) |
| `agents/gold_agent.py` | Modify | Add PostgreSQL export call (~20 lines) |
| `.env` | Modify | Add PostgreSQL connection config |
| `.env.example` | Modify | Add PostgreSQL config template |
| `requirements.txt` | Modify | Add psycopg2-binary, sqlalchemy |

---

**Your IDAMP pipeline now exports to PostgreSQL!** 🐘✨

Next Steps:
1. Install PostgreSQL locally or use cloud service
2. Create database and user
3. Create core/postgres_exporter.py
4. Update .env with connection string
5. Modify agents/gold_agent.py
6. Test with `pytest` or run full pipeline
7. Query PostgreSQL to verify tables created
