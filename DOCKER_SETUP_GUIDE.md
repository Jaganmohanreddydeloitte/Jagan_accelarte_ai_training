# Docker Setup Guide

Complete guide to building and running the Agentic Medallion Pipeline in Docker.

---

## Overview

The application is containerized with:
- **Dockerfile**: Builds a Python 3.11 image with all dependencies
- **docker-compose.yml**: Orchestrates multiple services (app, database, cache)
- **.dockerignore**: Excludes unnecessary files from image

---

## Prerequisites

1. **Docker** (version 20.10+)
   - [Install Docker Desktop](https://www.docker.com/products/docker-desktop)

2. **Docker Compose** (version 1.29+)
   - Usually included with Docker Desktop
   - Verify: `docker-compose --version`

3. **API Keys** (see Configuration section)

---

## Quick Start

### 1. Clone/Prepare Repository

```bash
cd ~/Desktop/Accelerate_with_ai_lab
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Or create `.env` with your configuration:

```bash
# LLM Configuration
LLM_PROVIDER=google
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Optional: Other LLM providers
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key

# Database (for Gold layer export)
DATABASE_PASSWORD=secure_password_here

# Application Settings
LOG_LEVEL=INFO
ENABLE_MONITORING=true
```

### 3. Build Docker Image

```bash
docker-compose build
```

This will:
- Download Python 3.11 base image
- Install all dependencies from `requirements.txt`
- Copy application code into container
- Create necessary directories

### 4. Start Services

```bash
docker-compose up
```

This will:
- Start PostgreSQL database
- Start Redis cache (optional)
- Start main Streamlit application
- Start pgAdmin (optional)

### 5. Access Application

Open browser: **http://localhost:8501**

### 6. Stop Services

```bash
docker-compose down
```

---

## Building & Running

### Build Only

```bash
docker-compose build
```

Or with no cache:

```bash
docker-compose build --no-cache
```

### Run in Foreground

```bash
docker-compose up
```

See logs in real-time. Press Ctrl+C to stop.

### Run in Background

```bash
docker-compose up -d
```

Then view logs:

```bash
docker-compose logs -f agentic-pipeline
```

### Run Specific Service

```bash
docker-compose up agentic-pipeline
```

(Without database/cache)

### Stop Services

```bash
docker-compose down
```

### Remove All Data

```bash
docker-compose down -v
```

(Removes volumes including database data)

---

## Configuration

### Environment Variables

Edit `.env` file before starting:

```bash
# LLM Providers
LLM_PROVIDER=google|openai|groq|github
GOOGLE_API_KEY=
OPENAI_API_KEY=
GROQ_API_KEY=
GITHUB_TOKEN=

# Models (override defaults)
GEMINI_MODEL=gemini-2.5-flash
OPENAI_MODEL=gpt-4o-mini
GROQ_MODEL=llama-3.3-70b-versatile

# Database
DATABASE_HOST=postgres
DATABASE_PORT=5432
DATABASE_NAME=agentic_pipeline
DATABASE_USER=pipeline_user
DATABASE_PASSWORD=your_secure_password

# Application
LOG_LEVEL=INFO
ENABLE_MONITORING=true
```

### Volume Mounts

```yaml
volumes:
  ./data:/app/data              # All pipeline data
  ./reports:/app/reports        # Generated reports
  ./audit_logs:/app/audit_logs  # Audit trail
  ./metrics:/app/metrics        # Performance metrics
```

### Port Mappings

| Service | Port | Purpose |
|---------|------|---------|
| Streamlit | 8501 | Main web application |
| PostgreSQL | 5432 | Database (optional) |
| pgAdmin | 5050 | Database UI (optional) |
| Redis | 6379 | Caching (optional) |

---

## Common Commands

### View Running Containers

```bash
docker-compose ps
```

### View Container Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs agentic-pipeline

# Follow logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100
```

### Execute Commands in Container

```bash
# Run tests
docker-compose exec agentic-pipeline pytest tests/

# Python REPL
docker-compose exec agentic-pipeline python

# Bash shell
docker-compose exec agentic-pipeline bash
```

### Remove Specific Service

```bash
docker-compose rm postgres
```

### Rebuild and Restart

```bash
docker-compose up --build -d
```

---

## Docker-Compose Structure

### Agentic Pipeline Service

- **Image**: Built from Dockerfile
- **Ports**: 8501 (Streamlit)
- **Volumes**: All data directories
- **Environment**: API keys, database config
- **Depends on**: PostgreSQL (optional)

### PostgreSQL Service

- **Image**: postgres:15-alpine
- **Port**: 5432
- **Volume**: postgres_data (persistent)
- **Database**: Configured via environment

### pgAdmin Service (Optional)

- **Image**: pgadmin4
- **Port**: 5050
- **Purpose**: Web UI for PostgreSQL management

### Redis Service (Optional)

- **Image**: redis:7-alpine
- **Port**: 6379
- **Purpose**: Caching layer

---

## Networking

All services connected via `pipeline-network` bridge network.

Services can reach each other:
- `agentic-pipeline` → `postgres:5432`
- `agentic-pipeline` → `redis:6379`
- `pgadmin` → `postgres:5432`

---

## Data Persistence

### PostgreSQL Data

Stored in `postgres_data` volume (survives container restart)

### Application Data

Mounted from local directories:
```
data/
├── landing/        (uploaded CSVs)
├── profiles/       (data profiles)
├── sttm/          (STTM rules)
├── bronze_layer/  (Bronze layer parquet)
├── silver_layer/  (Silver layer parquet)
└── gold_layer/    (Gold layer parquet)
```

### Metrics & Logs

```
metrics/           (Performance metrics)
audit_logs/        (Audit trail)
error_logs/        (Error logs)
recovery_state/    (Recovery checkpoints)
reports/           (Generated reports)
```

---

## Troubleshooting

### Port Already in Use

```bash
# Find what's using port 8501
lsof -i :8501

# Use different port
docker-compose up -p "8502:8501"
```

### Container Won't Start

```bash
# Check logs
docker-compose logs agentic-pipeline

# Rebuild without cache
docker-compose build --no-cache

# Start with verbose output
docker-compose up --verbose
```

### Database Connection Error

```bash
# Ensure PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Verify connection
docker-compose exec postgres psql -U pipeline_user -d agentic_pipeline
```

### Out of Disk Space

```bash
# Remove unused images
docker image prune

# Remove unused volumes
docker volume prune

# Remove everything (careful!)
docker system prune -a
```

### Permission Denied

```bash
# On Linux, add user to docker group
sudo usermod -aG docker $USER

# Restart Docker daemon
sudo systemctl restart docker
```

---

## Production Deployment

### Environment-Specific Compose Files

```bash
# Development
docker-compose -f docker-compose.yml up

# Production
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up
```

### Resource Limits

```yaml
services:
  agentic-pipeline:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

### Health Checks

Docker monitors container health:

```bash
# Check health status
docker-compose ps

# Container will restart if unhealthy
STATUS: Up 2 minutes (healthy)
```

### Logging & Monitoring

```yaml
logging:
  driver: "json-file"
  options:
    max-size: "10m"
    max-file: "3"
```

### Backup Database

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U pipeline_user agentic_pipeline > backup.sql

# Restore PostgreSQL
docker-compose exec -T postgres psql -U pipeline_user agentic_pipeline < backup.sql
```

---

## Advanced Usage

### Custom Network

```yaml
networks:
  pipeline-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

### Volume Driver Options

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: tmpfs
      device: tmpfs
```

### Multi-Stage Builds

For smaller images (not included by default):

```dockerfile
FROM python:3.11-slim as builder
# Build stage
...

FROM python:3.11-slim
# Runtime stage
COPY --from=builder /app /app
```

### Environment-Specific Overrides

```bash
# Use override compose file
docker-compose -f docker-compose.yml \
               -f docker-compose.override.yml up
```

---

## Scaling

### Horizontal Scaling

To run multiple instances:

```bash
docker-compose up --scale agentic-pipeline=3
```

### Load Balancing

Add nginx service:

```yaml
nginx:
  image: nginx:latest
  ports:
    - "80:80"
  depends_on:
    - agentic-pipeline
```

---

## Testing in Container

```bash
# Run tests
docker-compose exec agentic-pipeline pytest tests/ -v

# Run specific test
docker-compose exec agentic-pipeline pytest tests/test_performance_monitoring.py -v

# Run with coverage
docker-compose exec agentic-pipeline pytest --cov=core tests/
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Build Docker Image
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: docker/build-push-action@v2
        with:
          context: .
          push: true
          tags: myregistry/pipeline:${{ github.sha }}
```

---

## Security Best Practices

1. **Secrets**: Use `.env` file (not in git)
2. **Base Image**: Keep `python:3.11-slim` updated
3. **Permissions**: Don't run as root in container
4. **Network**: Use bridge network, not host
5. **Scanning**: Scan images for vulnerabilities
   ```bash
   docker scan image_name
   ```

---

## Performance Optimization

### Build Cache

```bash
# Use BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build .
```

### Image Size

- Base image: 125 MB (python:3.11-slim)
- Dependencies: ~200 MB
- Total: ~325 MB

### Container Startup

- First start: 5-10 seconds
- Subsequent: 2-3 seconds

---

## See Also

- [Dockerfile](Dockerfile)
- [docker-compose.yml](docker-compose.yml)
- [.dockerignore](.dockerignore)
- [Docker Documentation](https://docs.docker.com/)

---

## Summary

This Docker setup provides:
✅ Containerized application
✅ Optional PostgreSQL database
✅ Optional Redis caching
✅ Production-ready configuration
✅ Easy scaling and deployment
✅ Data persistence
✅ Health checks
✅ Logging and monitoring
