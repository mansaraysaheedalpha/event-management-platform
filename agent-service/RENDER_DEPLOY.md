# Agent Service - Render Deployment Guide

## Overview

The **Engagement Conductor Agent Service** is a FastAPI-based AI agent that monitors event engagement and executes interventions. This guide covers deploying it to Render.

**Service Details:**
- **Runtime:** Python 3.11+
- **Framework:** FastAPI
- **Port:** 8003
- **Dependencies:** Redis, PostgreSQL (TimescaleDB optional)

---

## Prerequisites

Before deploying, ensure you have:

1. **Render account** - https://render.com
2. **Anthropic API key** - https://console.anthropic.com
3. **Redis instance** - Your existing Upstash Redis works perfectly
4. **PostgreSQL database** - Can be created on Render

---

## Step 1: Create PostgreSQL Database on Render

1. Go to **Render Dashboard** → **New** → **PostgreSQL**

2. Configure the database:
   - **Name:** `agent-db` (or your preference)
   - **Database:** `agent_db`
   - **User:** Leave as default
   - **Region:** Same as your other services
   - **Plan:** Free tier works for testing, Starter ($7/mo) for production

3. Click **Create Database**

4. Once created, copy the **Internal Database URL** (for Render-to-Render communication) or **External Database URL** (for external access)

   Format will be like:
   ```
   postgresql://agent_db_user:PASSWORD@dpg-xxxxx-a.oregon-postgres.render.com/agent_db
   ```

> **Note on TimescaleDB:** Render's PostgreSQL doesn't include TimescaleDB extension. The service will work fine with regular PostgreSQL - it just won't create hypertables (time-series optimizations). For production with high data volume, consider [Timescale Cloud](https://www.timescale.com/cloud) (has free tier).

---

## Step 2: Create the Web Service

1. Go to **Render Dashboard** → **New** → **Web Service**

2. Connect your repository or use **Public Git repository**

3. Configure the service:

   | Setting | Value |
   |---------|-------|
   | **Name** | `agent-service` |
   | **Region** | Same as your other services |
   | **Branch** | `main` |
   | **Root Directory** | `agent-service` |
   | **Runtime** | `Python 3` |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
   | **Plan** | Starter ($7/mo) minimum - Free tier may timeout on AI calls |

---

## Step 3: Configure Environment Variables

In the Render service settings, add these environment variables:

### Required Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `REDIS_URL` | `rediss://default:AXC1AAI...@current-drake-28853.upstash.io:6379` | Your Upstash Redis URL (same as other services) |
| `DATABASE_URL` | `postgresql://user:pass@dpg-xxx.render.com/agent_db` | From Step 1 (use Internal URL) |
| `ANTHROPIC_API_KEY` | `sk-ant-api03-xxxxx` | Your Anthropic API key |
| `JWT_SECRET` | `your-secret-here` | **Must match your user-and-org-service** |
| `CORS_ORIGINS` | `https://your-frontend.onrender.com` | Your frontend URL(s), comma-separated |

### Optional Variables (with defaults)

| Variable | Default | Notes |
|----------|---------|-------|
| `ENGAGEMENT_THRESHOLD` | `0.6` | Minimum healthy engagement score |
| `ANOMALY_WARNING_THRESHOLD` | `0.6` | Warning alert threshold |
| `ANOMALY_CRITICAL_THRESHOLD` | `0.8` | Critical alert threshold |
| `MAX_REQUESTS_PER_MINUTE` | `60` | Rate limit |
| `MAX_LLM_COST_PER_HOUR` | `20.0` | Hourly cost cap in USD |
| `MAX_LLM_COST_PER_DAY` | `100.0` | Daily cost cap in USD |
| `LANGCHAIN_TRACING_V2` | `false` | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | `` | LangSmith API key (if tracing enabled) |

---

## Step 4: Create render.yaml (Optional - Infrastructure as Code)

For automated deployments, create a `render.yaml` in the `agent-service` directory:

```yaml
databases:
  - name: agent-db
    databaseName: agent_db
    plan: starter
    region: oregon

services:
  - type: web
    name: agent-service
    runtime: python
    region: oregon
    plan: starter
    rootDir: agent-service
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /health
    envVars:
      - key: REDIS_URL
        sync: false  # Set manually - shared with other services
      - key: DATABASE_URL
        fromDatabase:
          name: agent-db
          property: connectionString
      - key: ANTHROPIC_API_KEY
        sync: false  # Set manually
      - key: JWT_SECRET
        sync: false  # Set manually - must match other services
      - key: CORS_ORIGINS
        sync: false  # Set manually
      - key: PYTHON_VERSION
        value: "3.11"
```

---

## Step 5: Deploy

### Option A: Manual Deploy
1. Click **Create Web Service**
2. Render will build and deploy automatically
3. Wait for the build to complete (2-5 minutes)

### Option B: Blueprint Deploy (with render.yaml)
1. Go to **Render Dashboard** → **Blueprints**
2. Connect your repository
3. Render will detect `render.yaml` and create resources

---

## Step 6: Verify Deployment

### Health Check
```bash
curl https://agent-service.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "engagement-conductor-agent",
  "version": "0.1.0"
}
```

### Detailed Health Check
```bash
curl https://agent-service.onrender.com/health/detailed
```

This checks database and Redis connectivity.

### Readiness Check
```bash
curl https://agent-service.onrender.com/health/ready
```

---

## Step 7: Update Other Services

Update your other services to know about the agent service:

### Apollo Gateway
Add the agent service to your gateway configuration if needed.

### Real-time Service
Ensure it publishes to the correct Redis channels:
- `platform.events.chat.message.v1`
- `platform.events.poll.vote.v1`
- `platform.events.poll.closed.v1`
- `sync-events`

---

## Troubleshooting

### Common Issues

#### 1. "Connection refused" to Database
- Ensure you're using the **Internal Database URL** (not External)
- Check the database is in the same region as the service

#### 2. "Redis connection failed"
- Verify `REDIS_URL` uses `rediss://` (with SSL) for Upstash
- Ensure the URL is correctly formatted

#### 3. "JWT validation failed"
- Ensure `JWT_SECRET` matches your user-and-org-service exactly
- Check for trailing spaces or newlines in the secret

#### 4. "LLM request timeout"
- The free tier may timeout on Claude API calls
- Upgrade to Starter plan ($7/mo) for longer request timeouts
- The service has fallback to Haiku model for faster responses

#### 5. "CORS error" in browser
- Add your frontend URL to `CORS_ORIGINS`
- Multiple origins: `https://app.example.com,https://admin.example.com`

#### 6. High LLM Costs
- Monitor via `/metrics` endpoint
- Adjust `MAX_LLM_COST_PER_HOUR` and `MAX_LLM_COST_PER_DAY`
- Consider reducing intervention frequency

### View Logs
```bash
# In Render dashboard, go to your service → Logs
# Or use Render CLI:
render logs agent-service
```

---

## API Endpoints Reference

Once deployed, these endpoints are available:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe |
| `/health/ready` | GET | Readiness probe (checks dependencies) |
| `/health/detailed` | GET | Full component health status |
| `/metrics` | GET | Agent stats and cost metrics |
| `/api/v1/agent/sessions/register` | POST | Register a session with the agent |
| `/api/v1/agent/sessions/{id}/status` | GET | Get agent status for a session |
| `/api/v1/agent/sessions/{id}/mode` | PUT | Change agent mode (MANUAL/SEMI_AUTO/AUTO) |
| `/api/v1/interventions/manual` | POST | Manually trigger an intervention |
| `/api/v1/interventions/history/{session_id}` | GET | Get intervention history |

---

## Cost Estimates

### Render Costs
| Resource | Plan | Monthly Cost |
|----------|------|--------------|
| Web Service | Starter | $7 |
| PostgreSQL | Starter | $7 |
| **Total** | | **$14/mo** |

> Note: Free tier is available but may have timeout issues with LLM calls.

### Anthropic API Costs
| Model | Input | Output |
|-------|-------|--------|
| Claude Sonnet 4.5 | $3/MTok | $15/MTok |
| Claude Haiku | $1/MTok | $5/MTok |

Default limits: $20/hour, $100/day

---

## Production Checklist

Before going live:

- [ ] `JWT_SECRET` is set and matches other services
- [ ] `CORS_ORIGINS` contains only your production domains
- [ ] `ANTHROPIC_API_KEY` is a production key (not test key)
- [ ] Database backups are configured (Render does daily backups on paid plans)
- [ ] Cost limits (`MAX_LLM_COST_*`) are appropriate for your usage
- [ ] Health check endpoint is configured in Render
- [ ] Logging/monitoring is set up (consider LangSmith for agent tracing)
- [ ] Other services are publishing to the correct Redis channels

---

## Support

- **Render Documentation:** https://render.com/docs
- **Anthropic Documentation:** https://docs.anthropic.com
- **Upstash Redis:** https://docs.upstash.com/redis
