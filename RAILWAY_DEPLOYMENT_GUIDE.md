# Railway.app Deployment Guide

Complete step-by-step guide to deploy your event management platform to Railway.

**Estimated Time:** 2-3 hours
**Estimated Cost:** $50-150/month (includes $5/month free credit)
**Services Deployed:** 7 services (excluding oracle-ai-service)

---

## Prerequisites

Before starting, make sure you have:
- [ ] GitHub account with this repository pushed
- [ ] Railway.app account (sign up at railway.app)
- [ ] Credit card (for Railway, required after free tier)

---

## Phase 1: Set Up External Services (45 minutes)

Railway provides PostgreSQL and Redis, but you'll need external services for Kafka and object storage.

### 1.1 Messaging Setup (Kafka Alternative)

⚠️ **IMPORTANT UPDATE:** Upstash Kafka was discontinued on March 11, 2025. Choose one of these alternatives:

#### Option A: Upstash QStash (RECOMMENDED - Simplest) ⭐

**Why QStash?** Simplest solution, perfect for your email/background job use case, much cheaper

**Setup:**
1. Go to [upstash.com](https://upstash.com)
2. Sign up with GitHub or email
3. Click "QStash" tab
4. Click "Create" to create QStash instance
5. Note down credentials:
   - API Token (starts with `qstash_`)
   - Current Signing Key
   - Next Signing Key

**Cost:** Free tier (500 msgs/day), then $1 per 100k messages

**Pros:**
- ✅ Extremely simple (no Kafka complexity)
- ✅ Perfect for email sending
- ✅ Built-in retries and dead letter queue
- ✅ Much cheaper ($0-10/month vs $50-150/month)

**Cons:**
- ⚠️ Requires minor code changes (HTTP instead of Kafka client)
- ⚠️ Not for real-time streaming analytics

#### Option B: Confluent Cloud (Production Kafka)

**Why Confluent?** Official Kafka, industry standard, best reliability

**Setup:**
1. Go to [confluent.io/confluent-cloud](https://www.confluent.io/confluent-cloud/)
2. Sign up (get $400 free credits, or $1,000 via AWS Marketplace)
3. Click "Create Cluster" → Select "Basic" tier
4. Choose region close to your users
5. Create cluster

**Get Credentials:**
- Click "API Keys" → "Create Key"
- Save API Key and Secret
- Note Bootstrap Server URL (e.g., `pkc-xxxxx.us-east-1.aws.confluent.cloud:9092`)

**Create Topics:**
- Click "Topics" → "Create Topic"
- Create: `email-events`, `ad-events`, `waitlist-events`, `ticket-events`
- Partitions: 1, Retention: 7 days

**Cost:** Free for 1-3 months (using credits), then $50-150/month

#### Option C: Redpanda Serverless (Cost-Effective Kafka)

**Why Redpanda?** Kafka-compatible, 46% cheaper than Confluent, modern

**Setup:**
1. Go to [redpanda.com/try-redpanda](https://www.redpanda.com/try-redpanda)
2. Sign up (get $100 free credits)
3. Create Serverless cluster
4. Create topics
5. Get credentials

**Cost:** $100 free trial, then 46% cheaper than Confluent (~$40-100/month)

**See `KAFKA_ALTERNATIVES_2026.md` for detailed comparison and code examples**

### 1.2 Cloudflare R2 Setup (Object Storage - Free Tier Available)

**Why Cloudflare R2?** S3-compatible, free tier (10GB), cheaper than AWS S3, no egress fees

1. Go to [cloudflare.com](https://cloudflare.com) and sign in
2. Go to "R2" in the left sidebar
3. Click "Create bucket"
4. Name it: `your-app-name-files` (e.g., `eventapp-files`)
5. Click "Create bucket"

**Get Your Credentials:**
1. Click "Manage R2 API Tokens" (top right)
2. Click "Create API Token"
3. Select "Admin Read & Write" permissions
4. Click "Create API Token"
5. **Save these immediately** (you won't see them again):
   ```
   Access Key ID: xxxxxxxxxxxxx
   Secret Access Key: yyyyyyyyyyyyyyy
   Endpoint: https://xxxxxxxx.r2.cloudflarestorage.com
   ```

**Set Up Public Access (Optional):**
1. Go back to your bucket
2. Click "Settings" → "Public Access"
3. Click "Allow Access" if you want files to be publicly accessible
4. You'll get a public URL like: `https://pub-xxxxx.r2.dev`

### 1.3 Resend Email Setup (Free Tier: 100 emails/day)

**Why Resend?** Simple API, generous free tier, great deliverability

1. Go to [resend.com](https://resend.com)
2. Sign up with GitHub or email
3. Click "API Keys" → "Create API Key"
4. Name it "Production" and click "Add"
5. **Save the API key** (starts with `re_`)

**Add Your Domain (Optional but recommended):**
1. Click "Domains" → "Add Domain"
2. Enter your domain (e.g., `yourdomain.com`)
3. Add the DNS records shown to your domain registrar
4. Verify the domain
5. Now you can send from `noreply@yourdomain.com`

### 1.4 Stripe Setup (If using payments)

1. Go to [stripe.com](https://stripe.com) and sign up
2. Get your API keys:
   - Dashboard → Developers → API Keys
   - Copy "Publishable key" (starts with `pk_`)
   - Click "Reveal test key" and copy "Secret key" (starts with `sk_test_`)
3. For webhooks (set up after Railway deployment):
   - Dashboard → Developers → Webhooks
   - Add endpoint (you'll get the URL after deploying)

---

## Phase 2: Deploy to Railway (1 hour)

### 2.1 Create Railway Project

1. Go to [railway.app](https://railway.app) and sign in
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Authorize Railway to access your GitHub
5. Select your repository: `event-management-platform`
6. Railway will detect your services automatically

### 2.2 Add PostgreSQL Databases

**Add 3 PostgreSQL instances** (one for each service):

**Database 1: event-lifecycle-db**
1. In your Railway project, click "New" → "Database" → "Add PostgreSQL"
2. Rename it: Click on "Postgres" → Settings → Change name to `event-lifecycle-db`
3. Note: Railway auto-creates `DATABASE_URL` variable

**Database 2: user-org-db**
1. Click "New" → "Database" → "Add PostgreSQL"
2. Rename it to `user-org-db`

**Database 3: real-time-db**
1. Click "New" → "Database" → "Add PostgreSQL"
2. Rename it to `real-time-db`

**Cost:** ~$5/month per database = $15/month total

### 2.3 Add Redis

1. Click "New" → "Database" → "Add Redis"
2. Rename it to `redis`
3. Railway auto-creates `REDIS_URL` variable

**Cost:** ~$5/month

### 2.4 Deploy Services

Railway should have auto-detected your services. If not, add them manually:

#### Service 1: Apollo Gateway

1. Click "New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Root Directory:** `/apollo-gateway`
   - **Name:** `apollo-gateway`
3. Railway will automatically build using the Dockerfile

#### Service 2: User and Org Service

1. Click "New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Root Directory:** `/user-and-org-service`
   - **Name:** `user-and-org-service`

#### Service 3: Event Lifecycle Service

1. Click "New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Root Directory:** `/event-lifecycle-service`
   - **Name:** `event-lifecycle-service`

#### Service 4: Real-time Service

1. Click "New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Root Directory:** `/real-time-service`
   - **Name:** `real-time-service`

#### Service 5: Celery Worker (Background Tasks)

1. Click "New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Root Directory:** `/event-lifecycle-service`
   - **Name:** `celery-worker`
   - **Start Command:** `celery -A app.worker.celery_app worker --loglevel=info`

#### Service 6: Email Consumer (Kafka)

1. Click "New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Root Directory:** `/event-lifecycle-service`
   - **Name:** `email-consumer`
   - **Start Command:** `python run_email_consumer.py`

#### Service 7: (Optional) Oracle Consumer

Only if you're using the Oracle AI service later:
1. Click "New" → "GitHub Repo" → Select your repo
2. Configure:
   - **Root Directory:** `/oracle-ai-service`
   - **Name:** `oracle-consumer`
   - **Start Command:** `python run_consumer.py`

---

## Phase 3: Configure Environment Variables (30 minutes)

For each service, you need to set environment variables. Railway makes this easy with variable references.

### 3.1 Apollo Gateway Environment Variables

Click on `apollo-gateway` → "Variables" → Add these:

```bash
# Shared secrets
JWT_SECRET=your_jwt_secret_here_64_chars_min
JWT_REFRESH_SECRET=your_refresh_secret_here_64_chars_min
INTERNAL_API_KEY=your_internal_api_key_64_chars_min

# Environment
NODE_ENV=production

# Service URLs (Railway references)
USER_ORG_SERVICE_URL=${{user-and-org-service.RAILWAY_PUBLIC_DOMAIN}}/graphql
EVENT_LIFECYCLE_SERVICE_URL=${{event-lifecycle-service.RAILWAY_PUBLIC_DOMAIN}}/graphql
```

**Generate secrets:**
```bash
# In your terminal, generate random secrets:
openssl rand -hex 64  # Use this for JWT_SECRET
openssl rand -hex 64  # Use this for JWT_REFRESH_SECRET
openssl rand -hex 64  # Use this for INTERNAL_API_KEY
```

### 3.2 User and Org Service Environment Variables

Click on `user-and-org-service` → "Variables":

```bash
# Database (Railway reference)
DATABASE_URL=${{user-org-db.DATABASE_URL}}

# Redis (Railway reference)
REDIS_URL=${{redis.REDIS_URL}}

# Shared secrets (same as apollo-gateway)
JWT_SECRET=your_jwt_secret_here_64_chars_min
JWT_REFRESH_SECRET=your_refresh_secret_here_64_chars_min
INTERNAL_API_KEY=your_internal_api_key_64_chars_min

# Email (from Resend setup)
RESEND_API_KEY=re_your_resend_api_key
RESEND_FROM_EMAIL=noreply@yourdomain.com

# Environment
NODE_ENV=production
PORT=${{PORT}}  # Railway auto-injects
```

### 3.3 Event Lifecycle Service Environment Variables

Click on `event-lifecycle-service` → "Variables":

```bash
# Database (Railway reference)
DATABASE_URL_PROD=${{event-lifecycle-db.DATABASE_URL}}

# Redis (Railway reference)
REDIS_URL_PROD=${{redis.REDIS_URL}}

# Kafka (from Upstash setup)
KAFKA_BOOTSTRAP_SERVERS_PROD=your-cluster.upstash.io:9092
UPSTASH_KAFKA_USERNAME=your-upstash-username
UPSTASH_KAFKA_PASSWORD=your-upstash-password
UPSTASH_KAFKA_SASL_MECHANISM=SCRAM-SHA-256
UPSTASH_KAFKA_SECURITY_PROTOCOL=SASL_SSL

# S3/R2 Storage (from Cloudflare R2 setup)
AWS_ACCESS_KEY_ID=your_r2_access_key_id
AWS_SECRET_ACCESS_KEY=your_r2_secret_access_key
AWS_S3_BUCKET_NAME=your-bucket-name
AWS_S3_REGION=auto
AWS_S3_ENDPOINT_URL=https://your-account.r2.cloudflarestorage.com
AWS_S3_PUBLIC_URL=https://pub-xxxxx.r2.dev

# Shared secrets
JWT_SECRET=your_jwt_secret_here_64_chars_min
JWT_REFRESH_SECRET=your_refresh_secret_here_64_chars_min
INTERNAL_API_KEY=your_internal_api_key_64_chars_min

# Stripe (from Stripe setup)
STRIPE_SECRET_KEY=sk_test_your_stripe_key
STRIPE_PUBLISHABLE_KEY=pk_test_your_stripe_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret

# Email (from Resend)
RESEND_API_KEY=re_your_resend_api_key
RESEND_FROM_EMAIL=noreply@yourdomain.com

# Environment
ENV=prod
PORT=${{PORT}}

# Dummy values (required by config)
DATABASE_URL_LOCAL=dummy
REDIS_URL_LOCAL=dummy
KAFKA_BOOTSTRAP_SERVERS_LOCAL=dummy

# Inter-service URLs
REAL_TIME_SERVICE_URL_INTERNAL=${{real-time-service.RAILWAY_PRIVATE_DOMAIN}}

# Security
IP_HASH_SALT=$(openssl rand -hex 32)  # Generate a random salt
```

### 3.4 Real-time Service Environment Variables

Click on `real-time-service` → "Variables":

```bash
# Database (Railway reference)
DATABASE_URL=${{real-time-db.DATABASE_URL}}

# Redis (Railway reference)
REDIS_URL=${{redis.REDIS_URL}}

# Kafka (from Upstash)
KAFKA_BOOTSTRAP_SERVERS=${{event-lifecycle-service.KAFKA_BOOTSTRAP_SERVERS_PROD}}
UPSTASH_KAFKA_USERNAME=${{event-lifecycle-service.UPSTASH_KAFKA_USERNAME}}
UPSTASH_KAFKA_PASSWORD=${{event-lifecycle-service.UPSTASH_KAFKA_PASSWORD}}

# Shared secrets
JWT_SECRET=your_jwt_secret_here_64_chars_min
INTERNAL_API_KEY=your_internal_api_key_64_chars_min

# Inter-service URLs
EVENT_LIFECYCLE_SERVICE_URL_INTERNAL=${{event-lifecycle-service.RAILWAY_PRIVATE_DOMAIN}}
USER_ORG_SERVICE_URL_INTERNAL=${{user-and-org-service.RAILWAY_PRIVATE_DOMAIN}}

# Environment
NODE_ENV=production
PORT=${{PORT}}
```

### 3.5 Celery Worker Environment Variables

Click on `celery-worker` → "Variables":

**Copy ALL variables from `event-lifecycle-service`** (they use the same codebase)

Or use Railway's "Copy from Service" feature:
1. Click "Variables" → "Copy Variables"
2. Select `event-lifecycle-service`
3. Click "Copy"

### 3.6 Email Consumer Environment Variables

Click on `email-consumer` → "Variables":

**Copy ALL variables from `event-lifecycle-service`**

---

## Phase 4: Run Database Migrations (15 minutes)

### 4.1 Event Lifecycle Service Migration

1. Click on `event-lifecycle-service`
2. Go to "Settings" → "Deploy"
3. Add a "One-off Command":
   ```bash
   alembic upgrade head
   ```
4. Or use Railway CLI:
   ```bash
   railway run alembic upgrade head -s event-lifecycle-service
   ```

### 4.2 User and Org Service Migration

1. Click on `user-and-org-service`
2. Run one-off command:
   ```bash
   npx prisma migrate deploy
   ```

### 4.3 Real-time Service Migration

1. Click on `real-time-service`
2. Run one-off command:
   ```bash
   npx prisma migrate deploy
   ```

---

## Phase 5: Enable Public Access (10 minutes)

By default, Railway services are private. You need to enable public access:

### Enable Public Domains

For each service that needs public access:

**Apollo Gateway:**
1. Click on `apollo-gateway`
2. Go to "Settings" → "Networking"
3. Click "Generate Domain"
4. You'll get a URL like: `apollo-gateway-production-xxxx.up.railway.app`

**User and Org Service:**
1. Click on `user-and-org-service`
2. Settings → Networking → Generate Domain

**Event Lifecycle Service:**
1. Click on `event-lifecycle-service`
2. Settings → Networking → Generate Domain

**Real-time Service:**
1. Click on `real-time-service`
2. Settings → Networking → Generate Domain

**Copy these URLs** - you'll need them for frontend configuration and Apollo Gateway.

---

## Phase 6: Update Service URLs (5 minutes)

Now that you have public URLs, update the inter-service URLs:

### Update Apollo Gateway

Go to `apollo-gateway` → "Variables" and update:

```bash
USER_ORG_SERVICE_URL=https://user-and-org-service-production-xxxx.up.railway.app/graphql
EVENT_LIFECYCLE_SERVICE_URL=https://event-lifecycle-service-production-xxxx.up.railway.app/graphql
```

Railway will automatically redeploy when you change variables.

---

## Phase 7: Test Your Deployment (15 minutes)

### 7.1 Check Service Health

For each service, check if it's running:

**Apollo Gateway:**
```bash
curl https://your-apollo-gateway-url.up.railway.app/.well-known/apollo/server-health
```

Should return: `{"status":"pass"}`

**Event Lifecycle Service:**
```bash
curl https://your-event-lifecycle-url.up.railway.app/health
```

**Real-time Service:**
```bash
curl https://your-real-time-url.up.railway.app/health
```

**User and Org Service:**
```bash
curl https://your-user-org-url.up.railway.app/health
```

### 7.2 Test GraphQL Endpoint

Visit your Apollo Gateway URL in a browser:
```
https://your-apollo-gateway-url.up.railway.app
```

You should see the Apollo Studio interface.

Try a test query:
```graphql
query {
  __typename
}
```

### 7.3 Check Logs

For each service, click on "Deployments" → Latest deployment → "View Logs"

Look for:
- ✅ No error messages
- ✅ Database connections successful
- ✅ Kafka connections successful
- ✅ Redis connections successful

---

## Phase 8: Set Up Custom Domain (Optional, 15 minutes)

### 8.1 Add Domain to Railway

1. Go to your Apollo Gateway service
2. Settings → Networking → Custom Domain
3. Enter your domain: `api.yourdomain.com`
4. Railway will show you DNS records to add

### 8.2 Update DNS

Go to your domain registrar (Namecheap, GoDaddy, Cloudflare, etc.):

Add a CNAME record:
```
Name: api
Type: CNAME
Value: your-apollo-gateway-url.up.railway.app
TTL: 3600
```

Wait 5-15 minutes for DNS propagation.

### 8.3 SSL Certificate

Railway automatically provisions SSL certificates for custom domains via Let's Encrypt.

---

## Phase 9: Set Up Stripe Webhooks (If Using Payments)

1. Go to Stripe Dashboard → Developers → Webhooks
2. Click "Add endpoint"
3. Enter your webhook URL:
   ```
   https://your-event-lifecycle-url.up.railway.app/api/v1/stripe/webhook
   ```
4. Select events to listen for:
   - `checkout.session.completed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
5. Click "Add endpoint"
6. Copy the "Signing secret" (starts with `whsec_`)
7. Add it to Railway:
   - `event-lifecycle-service` → Variables → `STRIPE_WEBHOOK_SECRET`

---

## Phase 10: Monitor and Optimize

### 10.1 Set Up Monitoring

Railway provides built-in monitoring:
- CPU usage
- Memory usage
- Network traffic
- Deployment history

Check these regularly in the first few days.

### 10.2 Check Costs

1. Click on your profile → "Usage"
2. Monitor your usage and costs
3. Railway provides $5/month free credit

### 10.3 Set Up Alerts

1. Profile → Notifications
2. Enable email notifications for:
   - Deployment failures
   - High resource usage
   - Service crashes

---

## Cost Breakdown (Railway)

| Service | Type | Cost/Month |
|---------|------|------------|
| Apollo Gateway | Web Service | $10-15 |
| User & Org Service | Web Service | $10-15 |
| Event Lifecycle Service | Web Service | $15-20 |
| Real-time Service | Web Service | $15-20 |
| Celery Worker | Background Worker | $10-15 |
| Email Consumer | Background Worker | $5-10 |
| PostgreSQL (3 instances) | Database | $15 ($5 each) |
| Redis | Cache | $5 |
| **Subtotal (Railway)** | | **$85-115/month** |

### External Services:

| Service | Cost/Month |
|---------|------------|
| Messaging (QStash/Confluent/Redpanda) | $0-150 (see options above) |
| Cloudflare R2 | $0-5 (free tier: 10GB) |
| Resend Email | $0 (free tier: 100/day) |
| Stripe | Free (they take % of transactions) |
| **External Total** | **$0-15/month** |

### **Grand Total: $85-130/month**

With Railway's $5/month free credit: **$80-125/month**

---

## Optimization Tips

### Reduce Costs:

1. **Consolidate Databases:**
   - Use 2 PostgreSQL instances instead of 3
   - Put 2 databases in one instance (separate schemas)
   - **Savings: ~$5-10/month**

2. **Combine Workers:**
   - Run email-consumer and celery-worker in one service
   - **Savings: ~$5-10/month**

3. **Use Hibernation:**
   - Railway can hibernate services when not in use (Hobby plan)
   - Good for staging/dev environments

4. **Scale Down:**
   - Start with smaller instances
   - Scale up as traffic grows

### Performance Tips:

1. **Enable Railway's CDN** (if available)
2. **Use Connection Pooling** for databases (already configured in your code)
3. **Monitor Logs** for slow queries
4. **Add Database Indexes** as needed

---

## Troubleshooting

### Service Won't Start

**Check Logs:**
1. Click on service → Deployments → Latest → View Logs
2. Look for error messages

**Common Issues:**
- Missing environment variables
- Database connection failed
- Kafka connection failed

### Database Connection Errors

**Fix:**
1. Verify `DATABASE_URL` is set correctly
2. Check database is running: Click on database → "Metrics"
3. Try redeploying the service

### Kafka Connection Errors

**Fix:**
1. Verify Upstash credentials are correct
2. Check Upstash dashboard - is cluster running?
3. Verify `KAFKA_BOOTSTRAP_SERVERS` format: `your-cluster.upstash.io:9092`
4. Ensure SASL credentials are set

### Service Crashes/Restarts

**Check:**
1. Memory usage - might need to increase
2. CPU usage - might need to scale up
3. Logs for out-of-memory errors

**Fix:**
1. Click service → Settings → Resources
2. Increase memory allocation

### Migrations Failed

**Fix:**
1. Check database connection
2. Run migration command manually:
   ```bash
   railway run alembic upgrade head -s event-lifecycle-service
   ```
3. Check migration files for errors

---

## Next Steps After Deployment

1. **Frontend Deployment:**
   - Deploy your frontend to Vercel, Netlify, or Railway
   - Point it to your Railway backend URLs

2. **Custom Domain:**
   - Add your custom domain to Railway
   - Update DNS records

3. **Monitoring:**
   - Set up Sentry for error tracking
   - Add application performance monitoring (APM)

4. **CI/CD:**
   - Railway auto-deploys on git push
   - Configure branch deployments if needed

5. **Backups:**
   - Railway backs up databases daily
   - Consider additional backup strategy for critical data

6. **Scale:**
   - Monitor usage
   - Scale services as traffic grows
   - Consider moving to DigitalOcean or AWS when costs justify it

---

## Support and Resources

**Railway Documentation:**
- https://docs.railway.app

**Community:**
- Railway Discord: https://discord.gg/railway
- GitHub Issues: https://github.com/railwayapp/railway/issues

**Status:**
- https://status.railway.app

---

## Quick Reference: Railway CLI

Install Railway CLI:
```bash
npm install -g @railway/cli
```

**Useful Commands:**
```bash
# Login
railway login

# Link project
railway link

# Deploy
railway up

# Run migrations
railway run alembic upgrade head -s event-lifecycle-service

# View logs
railway logs -s event-lifecycle-service

# Open service in browser
railway open

# List services
railway status
```

---

## Congratulations! 🎉

Your event management platform is now live on Railway!

**What you've accomplished:**
- ✅ Deployed 7 microservices
- ✅ Set up 3 PostgreSQL databases
- ✅ Configured Redis caching
- ✅ Connected Kafka messaging
- ✅ Integrated S3-compatible storage
- ✅ Set up email service
- ✅ Configured Stripe payments
- ✅ All services communicating properly

**Your Production URLs:**
- Apollo Gateway: `https://your-gateway.up.railway.app`
- Event Service: `https://your-event-service.up.railway.app`
- Real-time Service: `https://your-realtime-service.up.railway.app`
- User Service: `https://your-user-service.up.railway.app`

You're ready to connect your frontend and start accepting real users! 🚀
