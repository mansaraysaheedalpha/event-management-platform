# Oracle AI Service - Render Deployment Guide

Complete guide for deploying the oracle-ai-service (AI matchmaking backend) to Render.

---

## Prerequisites

Before deploying, ensure you have:

1. **Render Account** - [Sign up at render.com](https://render.com)
2. **PostgreSQL Database** - Render managed or external
3. **Redis Instance** - Render managed or external (Upstash, Redis Cloud)
4. **API Keys**:
   - Tavily API key (for web search)
   - Anthropic API key (for LLM extraction)
   - (Optional) GitHub token for increased rate limits

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Render                               │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐   ┌─────────────────┐                  │
│  │  Web Service    │   │  Background     │                  │
│  │  (FastAPI)      │   │  Worker         │                  │
│  │  Port 8000      │   │  (Celery)       │                  │
│  └────────┬────────┘   └────────┬────────┘                  │
│           │                     │                            │
│           └──────────┬──────────┘                            │
│                      │                                       │
│           ┌──────────▼──────────┐                            │
│           │   Redis (Render)    │                            │
│           │   - Task Queue      │                            │
│           │   - Caching         │                            │
│           │   - Rate Limiting   │                            │
│           └──────────┬──────────┘                            │
│                      │                                       │
│           ┌──────────▼──────────┐                            │
│           │  PostgreSQL         │                            │
│           │  (Render Managed)   │                            │
│           └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────┘
```

---

## Step 1: Create PostgreSQL Database

### Option A: Render Managed PostgreSQL

1. Go to **Render Dashboard** → **New** → **PostgreSQL**
2. Configure:
   - **Name**: `oracle-ai-db`
   - **Database**: `oracle_ai`
   - **User**: `oracle_ai_user`
   - **Region**: Same as your web service
   - **Plan**: Starter ($7/mo) or higher for production
3. Click **Create Database**
4. Copy the **Internal Database URL** (starts with `postgres://`)

### Option B: External PostgreSQL (Supabase, Neon, etc.)

Use your existing PostgreSQL connection string.

---

## Step 2: Create Redis Instance

### Option A: Render Managed Redis

1. Go to **Render Dashboard** → **New** → **Redis**
2. Configure:
   - **Name**: `oracle-ai-redis`
   - **Max Memory Policy**: `allkeys-lru`
   - **Plan**: Starter ($10/mo) or higher
3. Copy the **Internal Redis URL**

### Option B: Upstash Redis (Recommended for cost)

1. Create account at [upstash.com](https://upstash.com)
2. Create a new Redis database
3. Copy the connection URL (TLS enabled)

---

## Step 3: Create Web Service (FastAPI)

1. Go to **Render Dashboard** → **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `oracle-ai-service` |
| **Root Directory** | `oracle-ai-service` |
| **Environment** | `Python 3` |
| **Region** | Same as database |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Plan** | Standard ($25/mo) minimum for AI workloads |

### Environment Variables

Add these in the **Environment** tab:

```bash
# ===========================================
# REQUIRED - Database
# ===========================================
ORACLE_DB_USER=oracle_ai_user
ORACLE_DB_PASSWORD=<from-render-postgres>
ORACLE_DB_HOST=<internal-hostname>.oregon-postgres.render.com
ORACLE_DB_PORT=5432
ORACLE_DB_NAME=oracle_ai

# ===========================================
# REQUIRED - Redis
# ===========================================
REDIS_URL=redis://<internal-hostname>:6379

# ===========================================
# REQUIRED - AI Services
# ===========================================
# Get from: https://tavily.com
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxx

# Get from: https://console.anthropic.com
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx

# ===========================================
# REQUIRED - Celery (same Redis, different DB numbers)
# ===========================================
CELERY_BROKER_URL=redis://<internal-hostname>:6379/1
CELERY_RESULT_BACKEND=redis://<internal-hostname>:6379/2

# ===========================================
# OPTIONAL - Enhanced Features
# ===========================================
# GitHub token increases rate limit from 60/hr to 5000/hr
GITHUB_PUBLIC_API_TOKEN=ghp_xxxxxxxxxxxxx

# ===========================================
# OPTIONAL - Rate Limiting (defaults shown)
# ===========================================
TAVILY_RATE_LIMIT=100
TAVILY_RATE_PERIOD_SECONDS=3600
GITHUB_RATE_LIMIT=50
GITHUB_RATE_PERIOD_SECONDS=3600
LLM_RATE_LIMIT=500
LLM_RATE_PERIOD_SECONDS=3600
USER_ENRICHMENT_RATE_LIMIT=5
USER_ENRICHMENT_RATE_PERIOD_SECONDS=3600
ENRICHMENT_MAX_PER_HOUR=100

# ===========================================
# OPTIONAL - Circuit Breaker (defaults shown)
# ===========================================
CIRCUIT_BREAKER_FAIL_MAX=5
CIRCUIT_BREAKER_TIMEOUT=60

# ===========================================
# OPTIONAL - Caching TTLs in seconds (defaults shown)
# ===========================================
TAVILY_CACHE_TTL_SECONDS=86400
GITHUB_CACHE_TTL_SECONDS=604800
ANALYTICS_CACHE_TTL_SECONDS=3600

# ===========================================
# OPTIONAL - Security (defaults shown)
# ===========================================
MAX_INPUT_STRING_LENGTH=1000
MAX_ARRAY_INPUT_LENGTH=50
ENRICHMENT_DATA_RETENTION_DAYS=365

# ===========================================
# OPTIONAL - Monitoring (if using Datadog)
# ===========================================
DATADOG_API_KEY=<your-datadog-api-key>
DATADOG_APP_KEY=<your-datadog-app-key>

# ===========================================
# OPTIONAL - Kafka (if using event streaming)
# ===========================================
KAFKA_BOOTSTRAP_SERVERS=<kafka-broker>:9092

# ===========================================
# Model Configuration
# ===========================================
SENTIMENT_MODEL_NAME=distilbert-base-uncased-finetuned-sst-2-english
```

4. Click **Create Web Service**

---

## Step 4: Create Background Worker (Celery)

1. Go to **Render Dashboard** → **New** → **Background Worker**
2. Connect same GitHub repository
3. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `oracle-ai-worker` |
| **Root Directory** | `oracle-ai-service` |
| **Environment** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `celery -A app.tasks worker --loglevel=info --concurrency=2` |
| **Plan** | Starter ($7/mo) or Standard ($25/mo) |

4. Add **same environment variables** as the web service
5. Click **Create Background Worker**

---

## Step 5: Create render.yaml (Infrastructure as Code)

Create `render.yaml` in your repository root for reproducible deployments:

```yaml
# render.yaml
services:
  # FastAPI Web Service
  - type: web
    name: oracle-ai-service
    runtime: python
    rootDir: oracle-ai-service
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: ORACLE_DB_USER
        fromDatabase:
          name: oracle-ai-db
          property: user
      - key: ORACLE_DB_PASSWORD
        fromDatabase:
          name: oracle-ai-db
          property: password
      - key: ORACLE_DB_HOST
        fromDatabase:
          name: oracle-ai-db
          property: host
      - key: ORACLE_DB_PORT
        fromDatabase:
          name: oracle-ai-db
          property: port
      - key: ORACLE_DB_NAME
        fromDatabase:
          name: oracle-ai-db
          property: database
      - key: REDIS_URL
        fromService:
          name: oracle-ai-redis
          type: redis
          property: connectionString
      - key: CELERY_BROKER_URL
        fromService:
          name: oracle-ai-redis
          type: redis
          property: connectionString
      - key: CELERY_RESULT_BACKEND
        fromService:
          name: oracle-ai-redis
          type: redis
          property: connectionString
      - key: TAVILY_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
      - key: GITHUB_PUBLIC_API_TOKEN
        sync: false
    autoDeploy: true

  # Celery Background Worker
  - type: worker
    name: oracle-ai-worker
    runtime: python
    rootDir: oracle-ai-service
    buildCommand: pip install -r requirements.txt
    startCommand: celery -A app.tasks worker --loglevel=info --concurrency=2
    envVars:
      - fromGroup: oracle-ai-env

databases:
  - name: oracle-ai-db
    plan: starter
    databaseName: oracle_ai
    user: oracle_ai_user

# Environment variable group for sharing between services
envVarGroups:
  - name: oracle-ai-env
    envVars:
      - key: TAVILY_API_KEY
        sync: false
      - key: ANTHROPIC_API_KEY
        sync: false
```

---

## Step 6: Database Migrations

After deployment, run migrations:

### Option A: One-time Job (Recommended)

1. Go to **Render Dashboard** → **New** → **Job**
2. Configure:
   - **Name**: `oracle-ai-migrate`
   - **Root Directory**: `oracle-ai-service`
   - **Command**: `alembic upgrade head`
3. Run manually after each schema change

### Option B: Auto-migrate on Deploy

Add to your `startCommand`:

```bash
alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Step 7: Health Check Configuration

Ensure your FastAPI app has a health endpoint:

```python
# app/main.py
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "oracle-ai-service",
        "enrichment_enabled": settings.enrichment_enabled,
    }
```

Configure in Render:
- **Health Check Path**: `/health`
- **Health Check Interval**: 30 seconds

---

## Step 8: Scaling Configuration

### Web Service Scaling

| Load Level | Instances | Plan |
|------------|-----------|------|
| Development | 1 | Starter ($7) |
| Production (low) | 1 | Standard ($25) |
| Production (medium) | 2-3 | Standard ($25 each) |
| Production (high) | 3-5 | Pro ($85 each) |

### Worker Scaling

| Event Size | Workers | Concurrency |
|------------|---------|-------------|
| < 100 attendees | 1 | 2 |
| 100-500 attendees | 2 | 4 |
| 500+ attendees | 3-4 | 4 |

Update start command for more concurrency:
```bash
celery -A app.tasks worker --loglevel=info --concurrency=4
```

---

## Step 9: Monitoring & Logs

### View Logs

```bash
# Using Render CLI
render logs oracle-ai-service --tail

# Or in Dashboard → Service → Logs
```

### Key Metrics to Monitor

1. **API Response Times** - Should be < 500ms for non-enrichment endpoints
2. **Worker Queue Length** - Check Redis `celery` queue
3. **Circuit Breaker State** - Monitor `/enrichment/health` endpoint
4. **Rate Limit Hits** - Check logs for `rate_limit_exceeded` audit events

### Datadog Integration (Optional)

If using Datadog, add the buildpack:
```yaml
# render.yaml
buildCommand: pip install ddtrace && pip install -r requirements.txt
startCommand: ddtrace-run uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

---

## Step 10: Cost Estimation

### Minimum Production Setup

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Web Service | Standard | $25 |
| Background Worker | Starter | $7 |
| PostgreSQL | Starter | $7 |
| Redis | Starter | $10 |
| **Total** | | **$49/month** |

### Recommended Production Setup

| Service | Plan | Monthly Cost |
|---------|------|--------------|
| Web Service (2x) | Standard | $50 |
| Background Worker (2x) | Standard | $50 |
| PostgreSQL | Standard | $20 |
| Redis | Standard | $25 |
| **Total** | | **$145/month** |

### External API Costs (Variable)

| Service | Pricing | Estimated Monthly |
|---------|---------|-------------------|
| Tavily | $0.01/search | $50-200 |
| Anthropic (Haiku) | $0.25/1M input tokens | $20-100 |
| **Total API** | | **$70-300** |

---

## Troubleshooting

### Common Issues

#### 1. "Enrichment disabled" warning

**Cause**: Missing `TAVILY_API_KEY` or `ANTHROPIC_API_KEY`

**Fix**: Add the environment variables in Render dashboard

#### 2. Worker not processing tasks

**Cause**: Redis connection or Celery config issue

**Fix**:
- Verify `CELERY_BROKER_URL` matches Redis URL
- Check worker logs for connection errors
- Ensure Redis allows connections from Render IPs

#### 3. Database connection timeout

**Cause**: Wrong host or firewall rules

**Fix**:
- Use **Internal** database URL (not external)
- Verify all services in same Render region

#### 4. Circuit breaker stuck open

**Cause**: External API consistently failing

**Fix**:
- Check Tavily/Anthropic status pages
- Wait for `CIRCUIT_BREAKER_TIMEOUT` (60s default)
- Monitor `/enrichment/health` endpoint

#### 5. Rate limit errors

**Cause**: Too many enrichment requests

**Fix**:
- Check `USER_ENRICHMENT_RATE_LIMIT` setting
- Increase `TAVILY_RATE_LIMIT` if you have higher plan
- Use batch endpoint with staggered processing

---

## Security Checklist

- [ ] All API keys stored as environment variables (not in code)
- [ ] PostgreSQL using internal URL (not exposed to internet)
- [ ] Redis using internal URL with password
- [ ] CORS configured for your frontend domain only
- [ ] Rate limiting enabled for all endpoints
- [ ] Audit logging enabled for compliance

---

## Post-Deployment Verification

Run these checks after deployment:

```bash
# 1. Health check
curl https://oracle-ai-service.onrender.com/health

# 2. Test enrichment endpoint (replace with valid user_id)
curl -X POST https://oracle-ai-service.onrender.com/enrichment/test-user-id \
  -H "Content-Type: application/json" \
  -d '{"name": "John Doe", "company": "Acme Inc", "role": "Engineer"}'

# 3. Check service status
curl https://oracle-ai-service.onrender.com/enrichment/health
```

Expected responses:
- Health: `{"status": "healthy", "enrichment_enabled": true}`
- Enrichment: `{"task_id": "...", "status": "queued"}`

---

## Support

- **Render Docs**: https://render.com/docs
- **Render Status**: https://status.render.com
- **Tavily Docs**: https://docs.tavily.com
- **Anthropic Docs**: https://docs.anthropic.com

---

*Generated for Event Dynamics Platform - Oracle AI Service v1.0*
