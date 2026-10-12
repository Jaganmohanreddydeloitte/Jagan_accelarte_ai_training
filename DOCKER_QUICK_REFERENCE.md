# Docker - Quick Reference

Fast lookup for Docker commands and operations.

---

## Basic Commands

### Build Image

```bash
# Build with default docker-compose.yml
docker-compose build

# Build without cache
docker-compose build --no-cache

# Build specific service
docker-compose build agentic-pipeline
```

### Start Services

```bash
# Start in foreground (see logs)
docker-compose up

# Start in background
docker-compose up -d

# Start specific service
docker-compose up agentic-pipeline

# Start with rebuild
docker-compose up --build -d
```

### Stop Services

```bash
# Stop (preserves containers)
docker-compose stop

# Stop specific service
docker-compose stop agentic-pipeline

# Stop and remove containers
docker-compose down

# Stop and remove with volumes
docker-compose down -v
```

---

## Viewing Information

### List Running Containers

```bash
docker-compose ps
```

### View Logs

```bash
# All services
docker-compose logs

# Specific service
docker-compose logs agentic-pipeline

# Follow logs (real-time)
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Follow last 50 lines
docker-compose logs -f --tail=50
```

### View Service Status

```bash
docker-compose ps

# Shows:
# - Service name
# - Status (Up, Down, Restarting)
# - Ports
# - Health (if configured)
```

---

## Executing Commands

### Run Command in Service

```bash
# Python shell
docker-compose exec agentic-pipeline python

# Bash shell
docker-compose exec agentic-pipeline bash

# Run tests
docker-compose exec agentic-pipeline pytest tests/ -v

# Run specific test
docker-compose exec agentic-pipeline pytest tests/test_performance_monitoring.py::TestMetricsCollector::test_initialize_collector

# Python command
docker-compose exec agentic-pipeline python -c "print('Hello')"
```

### Database Commands

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U pipeline_user -d agentic_pipeline

# List databases
docker-compose exec postgres psql -U pipeline_user -c "\l"

# Backup database
docker-compose exec postgres pg_dump -U pipeline_user agentic_pipeline > backup.sql

# Restore database
docker-compose exec -T postgres psql -U pipeline_user agentic_pipeline < backup.sql
```

### Check Service Health

```bash
# View all services
docker-compose ps

# Check specific service
docker-compose exec agentic-pipeline curl http://localhost:8501/_stcore/health

# Check database
docker-compose exec postgres pg_isready -U pipeline_user
```

---

## Management Commands

### Restart Services

```bash
# Restart all
docker-compose restart

# Restart specific
docker-compose restart agentic-pipeline

# Restart and rebuild
docker-compose up --build -d
```

### View Configuration

```bash
# Show config used
docker-compose config

# Show config for specific service
docker-compose config --services
```

### Scaling

```bash
# Run 3 instances of a service
docker-compose up --scale agentic-pipeline=3

# Note: Only works for stateless services
```

### Remove Services

```bash
# Remove stopped containers
docker-compose rm

# Remove without prompting
docker-compose rm -f

# Remove only database
docker-compose rm postgres
```

---

## Volumes & Data

### Inspect Volumes

```bash
# List volumes
docker volume ls

# Inspect volume
docker volume inspect agentic_pipeline_postgres_data

# Remove volume
docker volume rm agentic_pipeline_postgres_data
```

### Backup Data

```bash
# Backup application data
tar -czf backup-data.tar.gz data/

# Backup database
docker-compose exec postgres pg_dump -U pipeline_user agentic_pipeline > db-backup.sql

# Backup everything
docker-compose exec postgres pg_dump -U pipeline_user agentic_pipeline > backup.sql
tar -czf backup-all.tar.gz data/ audit_logs/ metrics/ reports/
```

### Restore Data

```bash
# Restore application data
tar -xzf backup-data.tar.gz

# Restore database
docker-compose exec -T postgres psql -U pipeline_user agentic_pipeline < backup.sql
```

---

## Troubleshooting

### View Image Layers

```bash
docker image history agentic_pipeline
```

### Inspect Service

```bash
docker-compose exec agentic-pipeline docker inspect self

# Or directly
docker inspect <container_id>
```

### Get Container ID

```bash
docker-compose ps --quiet agentic-pipeline
```

### Run Shell in Container

```bash
docker-compose exec agentic-pipeline /bin/bash

# Or
docker-compose run --rm agentic-pipeline bash
```

### View Resource Usage

```bash
docker stats
```

### Check Network

```bash
# List networks
docker network ls

# Inspect network
docker network inspect pipeline-network

# Test connectivity
docker-compose exec agentic-pipeline ping postgres
```

---

## Common Issues

### Port Already in Use

```bash
# Find what's using port 8501
lsof -i :8501

# Use different port (in docker-compose.yml or command line)
docker-compose up -p "8502:8501"
```

### Container Won't Start

```bash
# Check logs
docker-compose logs agentic-pipeline

# Rebuild
docker-compose build --no-cache

# Start with verbose
docker-compose up --verbose
```

### Out of Memory

```bash
# Check resource limits
docker stats

# Set limits in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 2G
```

### Database Connection Refused

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres

# Test connection
docker-compose exec postgres pg_isready -U pipeline_user
```

### Permission Denied (Linux)

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Restart Docker
sudo systemctl restart docker

# Log out and back in for changes to take effect
```

---

## Maintenance

### Clean Up

```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune

# Remove everything (careful!)
docker system prune -a
```

### Update Images

```bash
# Pull latest base images
docker-compose pull

# Rebuild
docker-compose build --no-cache

# Start
docker-compose up -d
```

### Monitor Logs

```bash
# Follow all logs
docker-compose logs -f

# Follow specific service
docker-compose logs -f agentic-pipeline

# Last hour of logs
docker-compose logs --since 1h

# Filter by pattern
docker-compose logs | grep ERROR
```

---

## Environment & Configuration

### View Environment

```bash
# Show docker-compose env
docker-compose config

# Check service environment
docker-compose exec agentic-pipeline env
```

### Update Environment

```bash
# Edit .env file
nano .env

# Restart services
docker-compose restart
```

### Override Compose File

```bash
# Use multiple compose files
docker-compose -f docker-compose.yml \
               -f docker-compose.override.yml up

# Use production config
docker-compose -f docker-compose.yml \
               -f docker-compose.prod.yml up -d
```

---

## Advanced

### Build with BuildKit

```bash
# Enable BuildKit for faster builds
DOCKER_BUILDKIT=1 docker build .

# Or globally
export DOCKER_BUILDKIT=1
docker-compose build
```

### Multi-Stage Builds

For smaller images (in Dockerfile):

```dockerfile
FROM python:3.11 as builder
# Build stage

FROM python:3.11-slim
# Runtime stage
COPY --from=builder /app /app
```

### Export/Import Images

```bash
# Save image to file
docker save agentic_pipeline > image.tar

# Load image from file
docker load < image.tar

# Export container filesystem
docker export container_name > container.tar
```

### Push to Registry

```bash
# Tag image
docker tag agentic_pipeline myregistry/pipeline:latest

# Push
docker push myregistry/pipeline:latest

# Pull from registry
docker pull myregistry/pipeline:latest
```

---

## Quick Recipes

### Local Development

```bash
# Start app without database
docker-compose up agentic-pipeline

# Mount local code for live reload
# (Use docker-compose.override.yml)
volumes:
  - ./app:/app/app
  - ./core:/app/core
```

### Production Deployment

```bash
# Build and push
docker-compose build
docker tag agentic_pipeline myregistry/pipeline:v1.0.0
docker push myregistry/pipeline:v1.0.0

# Deploy with docker-compose.prod.yml
docker-compose -f docker-compose.prod.yml up -d
```

### Database Backup on Schedule

```bash
# Cron job
0 2 * * * docker-compose exec postgres pg_dump -U pipeline_user agentic_pipeline > /backup/db-$(date +\%Y\%m\%d).sql
```

### Monitor Application

```bash
# Watch container status
watch 'docker-compose ps'

# Watch resource usage
watch 'docker stats --no-stream'

# Tail logs
docker-compose logs -f --tail=50
```

---

## Status

✅ Production-ready Docker setup
✅ Database included (optional)
✅ Caching support (optional)
✅ Health checks configured
✅ Logging enabled

---

## See Also

- [DOCKER_SETUP_GUIDE.md](DOCKER_SETUP_GUIDE.md) — Complete guide
- [docker-compose.yml](docker-compose.yml) — Service configuration
- [Dockerfile](Dockerfile) — Image definition
- [.dockerignore](.dockerignore) — Files to ignore
