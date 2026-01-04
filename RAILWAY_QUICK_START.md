# Railway Quick Start Checklist

Deploy your event management platform in 2-3 hours!

**Cost:** $80-130/month | **Time:** 2-3 hours | **Difficulty:** Easy

---

## Pre-Deployment (30 minutes)

### Step 1: External Services Setup

#### 1.1 Choose Your Messaging Solution

⚠️ **UPDATE:** Upstash Kafka was discontinued March 2025. Choose one option:

**Option A: Upstash QStash (RECOMMENDED - Simplest)** ⭐
- [ ] Sign up at [upstash.com](https://upstash.com)
- [ ] Click "QStash" tab → Create QStash instance
- [ ] Save API token and signing keys
- [ ] **Cost:** Free tier (500 msgs/day), then $1 per 100k messages

**Option B: Confluent Cloud (Production-Ready)**
- [ ] Sign up at [confluent.io/confluent-cloud](https://www.confluent.io/confluent-cloud/)
- [ ] Get $400 free credits (or $1,000 via AWS Marketplace)
- [ ] Create Kafka cluster (Basic tier)
- [ ] Create topics: `email-events`, `ad-events`, `waitlist-events`, `ticket-events`
- [ ] Save: Bootstrap servers, API Key, API Secret
- [ ] **Cost:** Free for 1-3 months, then $50-150/month

**Option C: Redpanda Serverless (Cost-Effective)**
- [ ] Sign up at [redpanda.com/try-redpanda](https://www.redpanda.com/try-redpanda)
- [ ] Get $100 free credits
- [ ] Create Serverless cluster
- [ ] Create topics
- [ ] **Cost:** 46% cheaper than Confluent

**See `KAFKA_ALTERNATIVES_2026.md` for detailed comparison**

#### 1.2 Cloudflare R2 (Free 10GB)
- [ ] Sign up at [cloudflare.com](https://cloudflare.com)
- [ ] Create R2 bucket (e.g., `eventapp-files`)
- [ ] Create API token (Admin Read & Write)
- [ ] Save: Access Key ID, Secret Access Key, Endpoint URL

#### 1.3 Resend Email (Free 100/day)
- [ ] Sign up at [resend.com](https://resend.com)
- [ ] Create API key
- [ ] (Optional) Add your domain
- [ ] Save: API key (starts with `re_`)

#### 1.4 Stripe (Optional - if using payments)
- [ ] Sign up at [stripe.com](https://stripe.com)
- [ ] Get test API keys (Dashboard → Developers → API Keys)
- [ ] Save: Publishable key (pk_test_...), Secret key (sk_test_...)

---

## Railway Setup (90 minutes)

### Step 2: Create Project

- [ ] Go to [railway.app](https://railway.app) and sign in with GitHub
- [ ] Click "New Project" → "Deploy from GitHub repo"
- [ ] Select your `event-management-platform` repository

### Step 3: Add Databases

- [ ] Add PostgreSQL #1, rename to `event-lifecycle-db`
- [ ] Add PostgreSQL #2, rename to `user-org-db`
- [ ] Add PostgreSQL #3, rename to `real-time-db`
- [ ] Add Redis, rename to `redis`

**Cost: $20/month**

### Step 4: Deploy Services

Add these services from GitHub repo (set root directory for each):

- [ ] **apollo-gateway** (root: `/apollo-gateway`)
- [ ] **user-and-org-service** (root: `/user-and-org-service`)
- [ ] **event-lifecycle-service** (root: `/event-lifecycle-service`)
- [ ] **real-time-service** (root: `/real-time-service`)
- [ ] **celery-worker** (root: `/event-lifecycle-service`, custom start command)
- [ ] **email-consumer** (root: `/event-lifecycle-service`, custom start command)

**Custom Start Commands:**
- **celery-worker:** `celery -A app.worker.celery_app worker --loglevel=info`
- **email-consumer:** `python run_email_consumer.py`

**Cost: $65-95/month**

### Step 5: Generate Secrets

In your terminal, generate random secrets:
```bash
openssl rand -hex 64  # JWT_SECRET
openssl rand -hex 64  # JWT_REFRESH_SECRET
openssl rand -hex 64  # INTERNAL_API_KEY
openssl rand -hex 32  # IP_HASH_SALT
```

Save these! You'll use them for ALL services.

### Step 6: Configure Environment Variables

#### For ALL Services (shared variables):
```bash
JWT_SECRET=<your_generated_secret>
JWT_REFRESH_SECRET=<your_generated_secret>
INTERNAL_API_KEY=<your_generated_secret>
IP_HASH_SALT=<your_generated_salt>
```

#### apollo-gateway:
```bash
NODE_ENV=production
USER_ORG_SERVICE_URL=${{user-and-org-service.RAILWAY_PUBLIC_DOMAIN}}/graphql
EVENT_LIFECYCLE_SERVICE_URL=${{event-lifecycle-service.RAILWAY_PUBLIC_DOMAIN}}/graphql
```

#### user-and-org-service:
```bash
DATABASE_URL=${{user-org-db.DATABASE_URL}}
REDIS_URL=${{redis.REDIS_URL}}
NODE_ENV=production
RESEND_API_KEY=re_your_key
RESEND_FROM_EMAIL=noreply@yourdomain.com
```

#### event-lifecycle-service:
```bash
DATABASE_URL_PROD=${{event-lifecycle-db.DATABASE_URL}}
REDIS_URL_PROD=${{redis.REDIS_URL}}
ENV=prod

# Choose ONE messaging option:

# Option A: QStash (Simplest)
QSTASH_TOKEN=your-qstash-token
QSTASH_CURRENT_SIGNING_KEY=your-signing-key
QSTASH_NEXT_SIGNING_KEY=your-next-signing-key

# Option B: Confluent Cloud
KAFKA_BOOTSTRAP_SERVERS_PROD=pkc-xxxxx.us-east-1.aws.confluent.cloud:9092
KAFKA_API_KEY=your-api-key
KAFKA_API_SECRET=your-api-secret
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN

# Option C: Redpanda Serverless
KAFKA_BOOTSTRAP_SERVERS_PROD=your-cluster.redpanda.cloud:9092
KAFKA_API_KEY=your-api-key
KAFKA_API_SECRET=your-api-secret
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=SCRAM-SHA-256

# R2 Storage (from Cloudflare)
AWS_ACCESS_KEY_ID=your-r2-access-key
AWS_SECRET_ACCESS_KEY=your-r2-secret-key
AWS_S3_BUCKET_NAME=your-bucket-name
AWS_S3_REGION=auto
AWS_S3_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
AWS_S3_PUBLIC_URL=https://pub-xxxxx.r2.dev

# Stripe
STRIPE_SECRET_KEY=sk_test_your_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_key
STRIPE_WEBHOOK_SECRET=whsec_your_secret

# Email
RESEND_API_KEY=re_your_key
RESEND_FROM_EMAIL=noreply@yourdomain.com

# Dummy values (required)
DATABASE_URL_LOCAL=dummy
REDIS_URL_LOCAL=dummy
KAFKA_BOOTSTRAP_SERVERS_LOCAL=dummy
```

#### real-time-service:
```bash
DATABASE_URL=${{real-time-db.DATABASE_URL}}
REDIS_URL=${{redis.REDIS_URL}}
NODE_ENV=production

# Copy Kafka vars from event-lifecycle-service
KAFKA_BOOTSTRAP_SERVERS=${{event-lifecycle-service.KAFKA_BOOTSTRAP_SERVERS_PROD}}
UPSTASH_KAFKA_USERNAME=${{event-lifecycle-service.UPSTASH_KAFKA_USERNAME}}
UPSTASH_KAFKA_PASSWORD=${{event-lifecycle-service.UPSTASH_KAFKA_PASSWORD}}
```

#### celery-worker & email-consumer:
- [ ] Copy ALL variables from `event-lifecycle-service`
- Use Railway's "Copy Variables" feature

**See `.env.railway.template` for complete list**

---

## Database Migrations (15 minutes)

### Step 7: Run Migrations

#### event-lifecycle-service:
```bash
railway run alembic upgrade head -s event-lifecycle-service
```

#### user-and-org-service:
```bash
railway run npx prisma migrate deploy -s user-and-org-service
```

#### real-time-service:
```bash
railway run npx prisma migrate deploy -s real-time-service
```

Or use Railway UI:
- Click service → Settings → Deploy → Run command (one-off)

---

## Enable Public Access (10 minutes)

### Step 8: Generate Public Domains

For each service, enable public access:
- [ ] apollo-gateway → Settings → Networking → Generate Domain
- [ ] user-and-org-service → Settings → Networking → Generate Domain
- [ ] event-lifecycle-service → Settings → Networking → Generate Domain
- [ ] real-time-service → Settings → Networking → Generate Domain

Copy the generated URLs (e.g., `xxx.up.railway.app`)

### Step 9: Update Apollo Gateway URLs

Go back to `apollo-gateway` variables and update:
```bash
USER_ORG_SERVICE_URL=https://user-and-org-xxx.up.railway.app/graphql
EVENT_LIFECYCLE_SERVICE_URL=https://event-lifecycle-xxx.up.railway.app/graphql
```

Railway will auto-redeploy.

---

## Testing (15 minutes)

### Step 10: Verify Deployment

Test each service health endpoint:

```bash
# Apollo Gateway
curl https://your-apollo-gateway.up.railway.app/.well-known/apollo/server-health

# Event Lifecycle
curl https://your-event-lifecycle.up.railway.app/health

# User & Org
curl https://your-user-org.up.railway.app/health

# Real-time
curl https://your-real-time.up.railway.app/health
```

All should return success!

### Step 11: Test GraphQL

Visit: `https://your-apollo-gateway.up.railway.app`

You should see Apollo Studio. Try this query:
```graphql
query {
  __typename
}
```

### Step 12: Check Logs

For each service:
- Click service → Deployments → Latest → View Logs
- Look for connection success messages
- No errors!

---

## Post-Deployment (Optional)

### Stripe Webhooks (if using payments)
- [ ] Go to Stripe Dashboard → Developers → Webhooks
- [ ] Add endpoint: `https://your-event-lifecycle.up.railway.app/api/v1/stripe/webhook`
- [ ] Select events: `checkout.session.completed`, `payment_intent.succeeded`
- [ ] Copy webhook signing secret → Add to Railway env vars

### Custom Domain (optional)
- [ ] Railway service → Settings → Networking → Add Custom Domain
- [ ] Add CNAME record to your DNS: `api.yourdomain.com` → `your-service.up.railway.app`
- [ ] Wait 5-15 min for DNS propagation
- [ ] Railway auto-provisions SSL certificate

### Monitoring
- [ ] Set up email notifications (Railway → Profile → Notifications)
- [ ] Monitor usage (Railway → Profile → Usage)
- [ ] Check costs regularly

---

## Cost Summary

| Item | Cost/Month |
|------|------------|
| Railway Services (7 services) | $65-95 |
| PostgreSQL (3 instances) | $15 |
| Redis | $5 |
| Messaging (QStash/Confluent/Redpanda) | $0-150 (see options) |
| Cloudflare R2 | $0-5 (free tier) |
| Resend Email | $0 (free tier) |
| **Railway Total** | **$85-115/month** |
| **Messaging** | **$0-150/month** |
| **Grand Total** | **$85-265/month** |
| Railway credit | -$5 |
| **Net Total** | **$80-260/month** |

**With QStash (Recommended):** $80-125/month
**With Confluent Free Tier:** $80-125/month (1-3 months)
**With Confluent Paid:** $130-275/month
**With Redpanda:** $120-225/month

---

## Troubleshooting

### Service won't start?
- Check logs for errors
- Verify all env variables are set
- Check database connection

### Database migration failed?
- Verify DATABASE_URL is correct
- Check database is running
- Try running migration again

### Kafka errors?
- Verify Upstash credentials
- Check SASL_MECHANISM is SCRAM-SHA-256
- Ensure SECURITY_PROTOCOL is SASL_SSL

### Service crashes?
- Check memory usage (Settings → Resources)
- Increase memory if needed
- Check logs for out-of-memory errors

---

## Success! 🎉

You now have:
- ✅ 7 microservices deployed
- ✅ 3 PostgreSQL databases
- ✅ Redis cache
- ✅ Kafka messaging
- ✅ S3-compatible storage
- ✅ Email service
- ✅ Payment processing

**Next Steps:**
1. Deploy your frontend (Vercel, Netlify)
2. Point frontend to Railway backend URLs
3. Test end-to-end flow
4. Launch! 🚀

**Need Help?**
- Full guide: See `RAILWAY_DEPLOYMENT_GUIDE.md`
- Railway Discord: https://discord.gg/railway
- Railway Docs: https://docs.railway.app

---

## Quick Commands

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Link project
railway link

# View logs
railway logs -s event-lifecycle-service

# Run command
railway run alembic upgrade head -s event-lifecycle-service

# Check status
railway status
```

Happy deploying! 🚀
