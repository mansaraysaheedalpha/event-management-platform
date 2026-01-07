# Deploying user-and-org-service to Render

This guide walks you through deploying the user-and-org-service to Render.

## Prerequisites

- A [Render account](https://render.com)
- Your code pushed to GitHub (Render connects to your repo)
- A Resend account for emails (https://resend.com)

---

## Step 1: Create PostgreSQL Database

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **New +** → **PostgreSQL**
3. Configure:
   - **Name**: `user-org-db`
   - **Database**: `user_org_db`
   - **User**: `user_org_user`
   - **Region**: Choose closest to your users
   - **Plan**: Free (for testing) or Starter ($7/mo for production)
4. Click **Create Database**
5. Wait for it to be ready, then copy the **Internal Database URL** (starts with `postgresql://`)

---

## Step 2: Create Redis Instance

1. Click **New +** → **Redis**
2. Configure:
   - **Name**: `user-org-redis`
   - **Region**: Same as your database
   - **Plan**: Free (for testing) or Starter for production
3. Click **Create Redis**
4. Copy the **Internal Redis URL** (starts with `redis://`)

---

## Step 3: Update Dockerfile for Production

Your Dockerfile needs to target the `runner` stage (not `builder`). Verify your Dockerfile has:

```dockerfile
# Production stage should be the default
FROM base AS runner
# ... (your production config)
USER nestjs
CMD ["node", "dist/main.js"]
```

---

## Step 4: Create the Web Service

1. Click **New +** → **Web Service**
2. Connect your GitHub repository
3. Configure:

### Basic Settings
| Field | Value |
|-------|-------|
| **Name** | `user-and-org-service` |
| **Region** | Same as your database |
| **Branch** | `main` (or your production branch) |
| **Root Directory** | `user-and-org-service` |
| **Runtime** | Docker |

### Build Settings
| Field | Value |
|-------|-------|
| **Dockerfile Path** | `./dockerfile` |
| **Docker Build Context** | `.` |

### Instance Type
- **Free**: For testing (spins down after 15 min inactivity)
- **Starter ($7/mo)**: For production (always on)

---

## Step 5: Configure Environment Variables

In the service settings, add these environment variables:

### Required Variables

| Variable | Value | Notes |
|----------|-------|-------|
| `NODE_ENV` | `production` | |
| `PORT` | `3001` | Render auto-detects, but set explicitly |
| `DATABASE_URL` | `postgresql://...` | Internal URL from Step 1 |
| `REDIS_URL` | `redis://...` | Internal URL from Step 2 |
| `JWT_SECRET` | (generate) | See "Generate Secrets" below |
| `JWT_REFRESH_SECRET` | (generate) | See "Generate Secrets" below |
| `INTERNAL_API_KEY` | (generate) | See "Generate Secrets" below |
| `ENCRYPTION_KEY` | (generate) | Must be exactly 64 hex chars |
| `FRONTEND_URL` | `https://your-frontend.com` | Your frontend domain |
| `API_BASE_URL` | `https://user-and-org-service.onrender.com` | Your Render service URL |
| `ALLOWED_ORIGINS` | `https://your-frontend.com` | Comma-separated if multiple |
| `RESEND_API_KEY` | `re_...` | From Resend dashboard |
| `RESEND_FROM_EMAIL` | `noreply@yourdomain.com` | Must be verified in Resend |

### Generate Secrets

Run these commands locally to generate secure secrets:

```bash
# JWT Secrets (64 bytes each)
node -e "console.log('JWT_SECRET=' + require('crypto').randomBytes(64).toString('hex'))"
node -e "console.log('JWT_REFRESH_SECRET=' + require('crypto').randomBytes(64).toString('hex'))"

# Internal API Key (32 bytes)
node -e "console.log('INTERNAL_API_KEY=' + require('crypto').randomBytes(32).toString('hex'))"

# Encryption Key (32 bytes = 64 hex chars)
node -e "console.log('ENCRYPTION_KEY=' + require('crypto').randomBytes(32).toString('hex'))"
```

---

## Step 6: Run Database Migrations

After your first deployment, you need to run Prisma migrations.

### Option A: Using Render Shell (Recommended)

1. Go to your service in Render
2. Click **Shell** tab
3. Run:
   ```bash
   npx prisma migrate deploy
   ```

### Option B: Add to Build Command

In your Render service settings, set the **Build Command** to:
```bash
pnpm install && pnpm run build && npx prisma generate && npx prisma migrate deploy
```

---

## Step 7: Configure Health Check

Render will automatically detect your health endpoint. Verify in settings:

| Field | Value |
|-------|-------|
| **Health Check Path** | `/health` |

---

## Step 8: Deploy

1. Click **Create Web Service** (or **Manual Deploy** if already created)
2. Watch the logs for any errors
3. Once deployed, your service will be at: `https://user-and-org-service.onrender.com`

---

## Step 9: Verify Deployment

### Check Health
```bash
curl https://user-and-org-service.onrender.com/health
```

### Check GraphQL
```bash
curl -X POST https://user-and-org-service.onrender.com/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ sayHello }"}'
```

Expected response:
```json
{"data":{"sayHello":"Hello World! GraphQL server is running."}}
```

---

## Troubleshooting

### Service won't start
1. Check **Logs** tab in Render
2. Common issues:
   - Missing environment variables (check all required vars are set)
   - Database connection failed (verify DATABASE_URL is internal URL)
   - Redis connection failed (verify REDIS_URL is internal URL)

### Database connection errors
- Use the **Internal Database URL**, not External
- Format: `postgresql://user:pass@hostname:5432/database`

### "ENCRYPTION_KEY must be 64 characters"
- Run: `node -e "console.log(require('crypto').randomBytes(32).toString('hex'))"`
- This generates exactly 64 hex characters

### Prisma migration fails
- Ensure DATABASE_URL is set correctly
- Try running migrations from Render Shell

---

## Cost Estimate (Production)

| Resource | Plan | Cost |
|----------|------|------|
| Web Service | Starter | $7/mo |
| PostgreSQL | Starter | $7/mo |
| Redis | Starter | $10/mo |
| **Total** | | **$24/mo** |

For testing, use Free tier (with limitations like spin-down after inactivity).

---

## Next Steps

After user-and-org-service is deployed:

1. **Update Apollo Gateway** to point to Render URL
2. **Deploy other services** following similar steps
3. **Set up custom domain** (optional)
4. **Configure Resend** domain verification for production emails

---

## Environment Variables Checklist

```
[ ] NODE_ENV=production
[ ] PORT=3001
[ ] DATABASE_URL=postgresql://...
[ ] REDIS_URL=redis://...
[ ] JWT_SECRET=<generated>
[ ] JWT_REFRESH_SECRET=<generated>
[ ] INTERNAL_API_KEY=<generated>
[ ] ENCRYPTION_KEY=<64-char-hex>
[ ] FRONTEND_URL=https://...
[ ] API_BASE_URL=https://...
[ ] ALLOWED_ORIGINS=https://...
[ ] RESEND_API_KEY=re_...
[ ] RESEND_FROM_EMAIL=noreply@...
```
