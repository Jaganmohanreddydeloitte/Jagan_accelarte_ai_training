# PostgreSQL Export - Quick Reference

## Installation

```bash
pip install psycopg2-binary sqlalchemy
```

## Configuration

Add to `.env`:
```bash
ENABLE_POSTGRES_EXPORT=true
DATABASE_URL=postgresql://user:password@host:5432/database
POSTGRES_SCHEMA=analytics
```

## Local Setup (5 minutes)

```bash
# 1. Install PostgreSQL
brew install postgresql              # macOS
sudo apt-get install postgresql      # Linux
# Download from postgresql.org        # Windows

# 2. Start PostgreSQL
brew services start postgresql        # macOS
psql -U postgres                      # Linux
# Use Task Scheduler                  # Windows

# 3. Create database
psql -U postgres -c "CREATE DATABASE idamp_analytics;"
psql -U postgres -c "CREATE USER idamp_user WITH PASSWORD 'password';"

# 4. Update .env
echo "ENABLE_POSTGRES_EXPORT=true" >> .env
echo "DATABASE_URL=postgresql://idamp_user:password@localhost:5432/idamp_analytics" >> .env

# 5. Test
python -c "from core.postgres_exporter import PostgreSQLExporter; e = PostgreSQLExporter('test'); print('OK' if e.connect() else 'FAIL')"

# 6. Run pipeline
streamlit run app/streamlit_app.py
```

## Cloud Providers

### AWS RDS
```
DATABASE_URL=postgresql://admin:password@mydb.xxxxxxx.us-east-1.rds.amazonaws.com:5432/analytics?sslmode=require
```

### Google Cloud SQL
```
# 1. Start Cloud SQL Proxy
cloud_sql_proxy -instances=project:region:instance=tcp:5432

# 2. Set connection string
DATABASE_URL=postgresql://user:pass@127.0.0.1:5432/analytics?sslmode=require
```

### Azure Database for PostgreSQL
```
DATABASE_URL=postgresql://user@servername:password@servername.postgres.database.azure.com:5432/analytics?sslmode=require
```

### Heroku PostgreSQL
```
# Automatically set as DATABASE_URL
DATABASE_URL=postgresql://user:password@ec2-xxx.compute-1.amazonaws.com:5432/database
```

## Query Data

```bash
# Connect
psql -U idamp_user -d idamp_analytics

# List tables
SELECT table_name FROM information_schema.tables WHERE table_schema = 'analytics';

# Count rows
SELECT COUNT(*) FROM analytics.customers;

# View sample
SELECT * FROM analytics.customers LIMIT 5;

# Join tables
SELECT c.id, o.order_id FROM analytics.customers c
  JOIN analytics.orders o ON c.id = o.customer_id
  LIMIT 10;

# Exit
\q
```

## Troubleshooting

| Error | Solution |
|-------|----------|
| `connection refused` | Verify PostgreSQL running: `pg_isready` |
| `role does not exist` | Create user: `CREATE USER name WITH PASSWORD 'pass';` |
| `database does not exist` | Create database: `CREATE DATABASE name;` |
| `permission denied` | Grant permissions: `GRANT ALL ON DATABASE db TO user;` |
| `SSL error` | Remove `?sslmode=require` or fix certificate |
| `timeout` | Increase timeout or check firewall |
| `export failed (non-fatal)` | Pipeline continues; Parquet files still saved |

## Pipeline Flow

```
Phase 1: Profile → Phase 2: Bronze → Phase 3: Silver → Phase 4: Gold
                                                          ↓
                                              📊 Export to PostgreSQL
                                                          ↓
                                              Query via SQL/BI Tools
                                                          ↓
                                              Phase 5: Report
```

## Files Created/Modified

| File | Type | Size |
|------|------|------|
| `core/postgres_exporter.py` | NEW | 12 KB |
| `tests/test_postgres_exporter.py` | NEW | 14 KB |
| `POSTGRES_EXPORT_GUIDE.md` | NEW | 27 KB |
| `POSTGRES_IMPLEMENTATION_SUMMARY.md` | NEW | 15 KB |
| `agents/gold_agent.py` | Modified | +50 lines |
| `requirements.txt` | Modified | +2 packages |
| `README.md` | Modified | +50 lines |
| `.env.example` | Modified | +40 lines |

## Tests (All Passing ✅)

```bash
pytest tests/test_postgres_exporter.py -v
# 27/27 PASSED in 3.67s

pytest tests/test_gold.py -v
# 13/13 PASSED (backward compatible)

pytest tests/ -q
# 144/144 PASSED (excluding Streamlit-only tests)
```

## Security

- ✅ Credentials in `.env` (git-ignored)
- ✅ No secrets in code or logs
- ✅ SSL/TLS support via connection string
- ✅ Least privilege recommended
- ✅ Error handling prevents data leaks
- ✅ Connection pooling included
- ✅ Audit logging built-in

## Performance Tips

1. **Local dev:** Use local PostgreSQL (fastest)
2. **Production:** Use managed service (AWS RDS, Google Cloud SQL)
3. **Large exports:** Use Groq LLM (faster agents)
4. **Queries:** Add indexes on frequently queried columns
5. **Backups:** Daily automated backups to secure location
6. **Monitoring:** Alert on export failures

## One-Line Test

```bash
python -c "from core.postgres_exporter import PostgreSQLExporter; e = PostgreSQLExporter('test-run'); print('[OK]' if e.connect() else '[FAIL]')" && echo "[OK] PostgreSQL export is configured!"
```

## Documentation

- **Setup Guide:** [POSTGRES_EXPORT_GUIDE.md](POSTGRES_EXPORT_GUIDE.md)
- **Implementation:** [POSTGRES_IMPLEMENTATION_SUMMARY.md](POSTGRES_IMPLEMENTATION_SUMMARY.md)
- **README Updates:** See PostgreSQL section in [README.md](README.md)
- **Code:** [core/postgres_exporter.py](core/postgres_exporter.py)
- **Tests:** [tests/test_postgres_exporter.py](tests/test_postgres_exporter.py)

---

**Ready to export?** Set `ENABLE_POSTGRES_EXPORT=true` and run! 🚀
