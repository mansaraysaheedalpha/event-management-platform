# Deploying Event-Lifecycle-Service to Render

This guide walks you through deploying the Event-Lifecycle-Service to Render.

## Prerequisites

1. A [Render](https://render.com) account
2. A PostgreSQL database (Render or external like Supabase, Railway)
3. A Redis instance (Upstash recommended for serverless)
4. AWS S3 bucket (or compatible storage) for file uploads
5. Stripe account for payment processing
6. Kafka cluster (Confluent Cloud recommended)
7. Resend account for email

## Step 1: Create a PostgreSQL Database

### Option A: Use Render PostgreSQL
1. Go to Render Dashboard → **New** → **PostgreSQL**
2. Configure:
   - **Name**: `event-lifecycle-db`
   - **Database Name**: `event_lifecycle_db`
   - **User**: `event_lifecycle_user`
   - **Region**: Same as your web service
   - **Plan**: Starter or higher
3. Click **Create Database**
4. Copy the **Internal Database URL** for later

### Option B: Use External PostgreSQL
Use your existing PostgreSQL URL from Supabase, Railway, or another provider.

## Step 2: Set Up Redis (Upstash)

1. Go to [Upstash Console](https://console.upstash.com/)
2. Create a new Redis database
3. Select a region close to your Render deployment
4. Copy the **Redis URL** (use the TLS URL starting with `rediss://`)

## Step 3: Set Up Kafka (Confluent Cloud)

1. Go to [Confluent Cloud](https://confluent.cloud/)
2. Create a new cluster
3. Create API keys for your cluster
4. Note down:
   - Bootstrap servers
   - API Key
   - API Secret

## Step 4: Deploy the Web Service

1. Go to Render Dashboard → **New** → **Web Service**
2. Connect your GitHub repository
3. Configure:
   - **Name**: `event-lifecycle-service`
   - **Region**: Same as database
   - **Branch**: `main`
   - **Root Directory**: `event-lifecycle-service`
   - **Runtime**: `Docker`
   - **Dockerfile Path**: `./Dockerfile`
   - **Plan**: Starter or higher

4. Add **Environment Variables**:

| Variable | Value | Notes |
|----------|-------|-------|
| `ENV` | `prod` | Required |
| `DATABASE_URL_PROD` | `postgresql://...` | Your PostgreSQL URL |
| `DATABASE_URL_LOCAL` | `dummy` | Required placeholder |
| `REDIS_URL_PROD` | `rediss://...` | Your Upstash URL |
| `REDIS_URL_LOCAL` | `dummy` | Required placeholder |
| `KAFKA_BOOTSTRAP_SERVERS_PROD` | `xxx.confluent.cloud:9092` | Confluent Cloud |
| `KAFKA_BOOTSTRAP_SERVERS_LOCAL` | `dummy` | Required placeholder |
| `KAFKA_API_KEY` | Your API key | Confluent Cloud |
| `KAFKA_API_SECRET` | Your API secret | Confluent Cloud |
| `KAFKA_SECURITY_PROTOCOL` | `SASL_SSL` | For Confluent Cloud |
| `KAFKA_SASL_MECHANISM` | `PLAIN` | For Confluent Cloud |
| `JWT_SECRET` | 64+ char secret | **MUST match user-and-org-service!** |
| `INTERNAL_API_KEY` | 64+ char secret | **MUST match user-and-org-service!** |
| `IP_HASH_SALT` | 64 char hex | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALLOWED_ORIGINS` | `https://yourfrontend.com` | Comma-separated |
| `FRONTEND_URL` | `https://yourfrontend.com` | For redirects |
| `AWS_ACCESS_KEY_ID` | Your key | AWS/S3 compatible |
| `AWS_SECRET_ACCESS_KEY` | Your secret | AWS/S3 compatible |
| `AWS_S3_BUCKET_NAME` | `your-bucket` | S3 bucket name |
| `AWS_S3_REGION` | `us-east-1` | S3 region |
| `AWS_S3_ENDPOINT_URL` | *(empty)* | Leave empty for AWS |
| `STRIPE_SECRET_KEY` | `sk_live_...` | Production Stripe key |
| `STRIPE_PUBLISHABLE_KEY` | `pk_live_...` | Production Stripe key |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` | From Stripe webhook setup |
| `RESEND_API_KEY` | `re_...` | Your Resend API key |
| `RESEND_FROM_DOMAIN` | `noreply@yourdomain.com` | Verified domain |
| `REAL_TIME_SERVICE_URL_INTERNAL` | `https://real-time.onrender.com` | When deployed |
| `USER_SERVICE_URL` | `https://user-org.onrender.com` | When deployed |

5. Click **Create Web Service**

## Step 5: Set Up Health Check

Render should auto-detect the health check, but you can configure:
- **Health Check Path**: `/health`
- **Health Check Interval**: 30 seconds

## Step 6: Configure Stripe Webhooks

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/webhooks)
2. Click **Add endpoint**
3. Enter your webhook URL: `https://your-service.onrender.com/api/v1/webhooks/stripe`
4. Select events to listen to:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `payment_intent.canceled`
   - `charge.refunded`
   - `refund.succeeded`
   - `refund.failed`
5. Also add endpoint for offers: `https://your-service.onrender.com/api/v1/offer-webhooks/stripe`
   - `checkout.session.completed`
   - `checkout.session.expired`
6. Copy the **Signing secret** and update `STRIPE_WEBHOOK_SECRET` in Render

## Step 7: Run Database Migrations

After deployment, you may need to run Alembic migrations:

1. Open Render Shell for your service
2. Run:
```bash
alembic upgrade head
```

Or configure a **Pre-Deploy Command** in Render:
```bash
alembic upgrade head
```

## Step 8: Deploy Celery Worker (Optional)

If you need background task processing:

1. Create another **Web Service** or **Background Worker**
2. Use the same repository and root directory
3. Set **Docker Command** to:
```bash
celery -A app.worker.celery_app worker --loglevel=info
```
4. Add the same environment variables

## Verification

1. Check the service is running:
```bash
curl https://your-service.onrender.com/health
```

2. Check the API documentation:
```
https://your-service.onrender.com/docs
```

## Troubleshooting

### Service won't start
- Check logs in Render dashboard
- Verify all required environment variables are set
- Ensure DATABASE_URL_PROD is correct

### Database connection errors
- Verify the database is running and accessible
- Check if the connection string is correct
- For Render PostgreSQL, use the Internal URL

### Webhook failures
- Verify STRIPE_WEBHOOK_SECRET matches Stripe dashboard
- Check webhook endpoint URL is correct
- Review webhook logs in Stripe dashboard

### CORS errors
- Ensure ALLOWED_ORIGINS includes your frontend URL
- Don't include trailing slashes in URLs

## Environment Variables Checklist

- [ ] `ENV=prod`
- [ ] `DATABASE_URL_PROD` (your PostgreSQL URL)
- [ ] `DATABASE_URL_LOCAL=dummy`
- [ ] `REDIS_URL_PROD` (your Upstash URL)
- [ ] `REDIS_URL_LOCAL=dummy`
- [ ] `KAFKA_BOOTSTRAP_SERVERS_PROD`
- [ ] `KAFKA_BOOTSTRAP_SERVERS_LOCAL=dummy`
- [ ] `KAFKA_API_KEY`
- [ ] `KAFKA_API_SECRET`
- [ ] `KAFKA_SECURITY_PROTOCOL=SASL_SSL`
- [ ] `KAFKA_SASL_MECHANISM=PLAIN`
- [ ] `JWT_SECRET` (same as user-and-org-service)
- [ ] `INTERNAL_API_KEY` (same as user-and-org-service)
- [ ] `IP_HASH_SALT`
- [ ] `ALLOWED_ORIGINS`
- [ ] `FRONTEND_URL`
- [ ] `AWS_ACCESS_KEY_ID`
- [ ] `AWS_SECRET_ACCESS_KEY`
- [ ] `AWS_S3_BUCKET_NAME`
- [ ] `AWS_S3_REGION`
- [ ] `STRIPE_SECRET_KEY`
- [ ] `STRIPE_PUBLISHABLE_KEY`
- [ ] `STRIPE_WEBHOOK_SECRET`
- [ ] `RESEND_API_KEY`
- [ ] `RESEND_FROM_DOMAIN`
