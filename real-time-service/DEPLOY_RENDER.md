# Deploying real-time-service to Render

This guide walks you through deploying the real-time-service (NestJS WebSocket + Kafka consumer) to Render.

## Prerequisites

Before deploying, ensure you have:
- A Render account (https://render.com)
- PostgreSQL database (Render managed or external like Neon)
- Redis instance (Upstash recommended since Render doesn't offer managed Redis)
- Kafka cluster (Confluent Cloud recommended)
- The user-and-org-service and event-lifecycle-service already deployed

## Step 1: Create a New Web Service on Render

1. Go to your Render Dashboard
2. Click **New +** > **Web Service**
3. Connect your GitHub repository
4. Select the `event-management-platform` repository

## Step 2: Configure the Service

Use these settings:

| Setting | Value |
|---------|-------|
| **Name** | `real-time-service` |
| **Region** | Choose closest to your users |
| **Root Directory** | `real-time-service` |
| **Runtime** | `Node` |
| **Build Command** | `npm install && npx prisma generate && npm run build` |
| **Start Command** | `npm run start:prod` |
| **Instance Type** | Start with **Starter** ($7/month) or **Standard** for production |

## Step 3: Configure Environment Variables

Add the following environment variables in the Render dashboard:

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `NODE_ENV` | Environment mode | `production` |
| `PORT` | Server port (Render sets this automatically) | `3002` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/realtime_db?sslmode=require` |
| `REDIS_URL` | Redis connection string (Upstash) | `rediss://default:xxx@xxx.upstash.io:6379` |
| `JWT_SECRET` | JWT signing secret (same as other services) | `your-jwt-secret` |
| `INTERNAL_API_KEY` | API key for service-to-service auth | `your-internal-api-key` |

### Kafka Configuration (Confluent Cloud)

| Variable | Description | Example |
|----------|-------------|---------|
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka broker addresses | `pkc-xxx.region.confluent.cloud:9092` |
| `KAFKA_API_KEY` | Confluent Cloud API key | `your-kafka-api-key` |
| `KAFKA_API_SECRET` | Confluent Cloud API secret | `your-kafka-api-secret` |

### Service URLs (Internal Communication)

| Variable | Description | Example |
|----------|-------------|---------|
| `USER_ORG_SERVICE_URL` | URL to user-and-org-service | `https://user-and-org-service.onrender.com` |
| `EVENT_LIFECYCLE_SERVICE_URL` | URL to event-lifecycle-service | `https://event-lifecycle-service.onrender.com` |
| `EVENT_SERVICE_URL` | Alias for event-lifecycle-service | `https://event-lifecycle-service.onrender.com` |

### CORS Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `ALLOWED_ORIGINS` | Comma-separated allowed origins | `https://yourdomain.com,https://www.yourdomain.com` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TRANSLATION_API_KEY` | API key for translation service | (empty - translation disabled) |

## Step 4: Database Setup

The real-time-service has its own Prisma schema. You need a separate database for it.

### Option A: Use Render PostgreSQL
1. Create a new PostgreSQL database on Render
2. Copy the **Internal Database URL** for `DATABASE_URL`

### Option B: Use External PostgreSQL (Neon, Supabase, etc.)
1. Create a new database on your provider
2. Use the connection string with `?sslmode=require`

### Run Migrations
After the first deployment, you may need to run migrations:
```bash
# In the Render Shell or locally with DATABASE_URL set
npx prisma migrate deploy
```

## Step 5: Redis Setup (Upstash)

Since Render doesn't provide managed Redis:

1. Go to https://upstash.com
2. Create a new Redis database
3. Copy the **Redis URL** (starts with `rediss://` for TLS)
4. Use this URL for the `REDIS_URL` environment variable

**Important:** Use `rediss://` (with double 's') for TLS connections.

## Step 6: Kafka Setup (Confluent Cloud)

1. Go to https://confluent.cloud
2. Create a cluster if you haven't already
3. Create API keys for the real-time-service
4. Get the bootstrap server address from cluster settings
5. Create the required topic: `giveaway.events.v1`

## Step 7: Deploy

1. Click **Create Web Service**
2. Wait for the build and deployment to complete
3. Check the logs for any errors

## Step 8: Verify Deployment

1. Check the health endpoint:
   ```
   https://real-time-service.onrender.com/health
   ```

2. Check the logs for:
   - "Kafka producer connected successfully"
   - "Real-time service is running on: ..."

## WebSocket Considerations

The real-time-service uses WebSockets (Socket.io). Render supports WebSocket connections, but note:

- WebSocket connections may timeout after periods of inactivity
- The service uses Redis adapter for Socket.io, enabling horizontal scaling
- Clients should implement reconnection logic

## Troubleshooting

### Service crashes on startup
- Check if all required environment variables are set
- Verify database URL is correct and accessible
- Check Kafka credentials are valid

### Kafka connection errors
- Ensure `KAFKA_BOOTSTRAP_SERVERS` includes the port (`:9092`)
- Verify `KAFKA_API_KEY` and `KAFKA_API_SECRET` are correct
- Check that the Kafka cluster allows connections from Render IPs

### Redis connection errors
- Ensure using `rediss://` protocol for Upstash (TLS)
- Check that the Redis URL is complete and correct

### WebSocket connections failing
- Ensure `ALLOWED_ORIGINS` includes your frontend domain
- Check that the client is connecting to the correct URL
- Verify Render's load balancer isn't blocking WebSocket upgrades

### Database connection errors
- Ensure `?sslmode=require` is in the DATABASE_URL
- Verify the database allows connections from Render IPs
- Check that the database exists and migrations have run

## Architecture Notes

The real-time-service:
- Exposes WebSocket endpoints for real-time features (chat, polls, Q&A, etc.)
- Consumes Kafka events from other services
- Uses Redis for Socket.io pub/sub (enabling horizontal scaling)
- Communicates with user-and-org-service and event-lifecycle-service via REST

This service does NOT go through Apollo Gateway - clients connect directly via WebSocket.
