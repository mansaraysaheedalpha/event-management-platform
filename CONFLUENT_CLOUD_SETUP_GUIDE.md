# Confluent Cloud Setup Guide - Step-by-Step

Complete walkthrough with answers to every question during Confluent Cloud Kafka cluster setup.

**Time:** 15-20 minutes
**Cost:** FREE (using $400 credits)

---

## Phase 1: Account Creation (5 minutes)

### Step 1: Sign Up

1. Go to [https://www.confluent.io/confluent-cloud/](https://www.confluent.io/confluent-cloud/)

2. Click **"Start Free"** or **"Try Free"**

### Step 2: Account Information

**You'll be asked:**

| Question | What to Enter | Example |
|----------|---------------|---------|
| **First Name** | Your first name | John |
| **Last Name** | Your last name | Doe |
| **Email** | Your email address | john.doe@yourdomain.com |
| **Password** | Strong password (min 8 chars) | YourStrongP@ssw0rd |
| **Company Name** | Your company or project name | EventConnect (or "Personal Project") |
| **Job Title** | Your role | Developer / Founder / CTO |
| **Country** | Your country | United States |

3. Check the box for **Terms of Service**
4. Click **"Start Free Trial"**

### Step 3: Email Verification

1. Check your email inbox
2. Click the verification link
3. You'll be redirected back to Confluent Cloud

---

## Phase 2: Get Free Credits (Choose One)

### Option A: Standard Sign-Up ($400 credits)

1. After email verification, Confluent automatically adds **$400 in free credits**
2. These expire in **30 days**
3. No credit card required initially (but needed to continue after trial)

### Option B: AWS Marketplace ($1,000 credits) - RECOMMENDED ⭐

**Why?** Get $1,000 instead of $400!

**Steps:**
1. Go to [AWS Marketplace - Confluent Cloud](https://aws.amazon.com/marketplace/pp/prodview-g5ujul6iovvcy)
2. Click **"View purchase options"**
3. Click **"Subscribe"**
4. Accept terms
5. Click **"Set up your account"**
6. Follow prompts to link Confluent Cloud account
7. You'll get **$1,000 in credits for 30 days**

**Answers for AWS Marketplace:**
- **AWS Account:** Use your existing AWS account (or create free tier account)
- **Region:** Any (doesn't affect Confluent cluster location)
- **Subscription:** Free tier / Pay as you go

---

## Phase 3: Create Your First Cluster (10 minutes)

### Step 1: Welcome Screen

After logging in, you'll see the **Confluent Cloud Dashboard**.

Click **"Create cluster"** or **"Add cluster"**

---

### Step 2: Choose Cluster Type

**You'll see 3 options:**

| Option | Description | Our Choice |
|--------|-------------|------------|
| **Basic** | Limited features, lowest cost | ✅ **Choose This** |
| **Standard** | More features, higher cost | ❌ Too expensive |
| **Dedicated** | Full control, highest cost | ❌ Overkill |

**What to Choose:** **Basic**

**Why?**
- ✅ Free with your credits
- ✅ Perfect for development and small production
- ✅ Up to 5 TB storage
- ✅ Up to 1 GB/s throughput
- ✅ Supports all core Kafka features

Click **"Begin configuration"**

---

### Step 3: Choose Cloud Provider

**You'll see 3 options:**

| Provider | Our Recommendation |
|----------|-------------------|
| **AWS** | ✅ **Choose this** (most popular, best integration) |
| **Google Cloud** | ⚠️ Alternative (if you use GCP) |
| **Azure** | ⚠️ Alternative (if you use Azure) |

**What to Choose:** **Amazon Web Services (AWS)**

**Why?**
- Most popular and reliable
- Best integration with other services
- Your Railway services can easily connect to AWS regions

Click **"Continue"**

---

### Step 4: Choose Region

**Question:** "Select a region"

**What to Choose:** Select region **closest to your users** or where Railway will deploy

**Recommendations:**

| Your Users Location | Recommended Region |
|---------------------|-------------------|
| **United States (East Coast)** | `us-east-1` (N. Virginia) ⭐ MOST COMMON |
| **United States (West Coast)** | `us-west-2` (Oregon) |
| **Europe** | `eu-west-1` (Ireland) |
| **Asia (Singapore/India)** | `ap-southeast-1` (Singapore) |

**For most people:** Choose **`us-east-1` (N. Virginia)**

**Why?**
- ✅ Most popular region
- ✅ Lowest latency for US users
- ✅ Most Railway deployments use this
- ✅ Best availability

Click **"Continue"**

---

### Step 5: Cluster Name

**Question:** "Cluster name"

**What to Enter:** A descriptive name for your cluster

**Recommendations:**
- `eventapp-prod` (if this is production)
- `eventapp-staging` (if this is staging/test)
- `my-kafka-cluster` (generic)

**Example:** `eventapp-prod`

**Best Practice:** Use lowercase, hyphens, descriptive names

---

### Step 6: Review and Launch

You'll see a summary:

```
Cluster Type: Basic
Cloud Provider: AWS
Region: us-east-1
Cluster Name: eventapp-prod
Estimated Cost: $0.00/month (using credits)
```

**Question:** "Add payment method"

**What to Do:**
- **Option A:** Click **"Skip for now"** (if available)
- **Option B:** Add credit card (required, but won't be charged during free trial)

**If adding credit card:**
- Enter card details
- You won't be charged until:
  - Your $400 (or $1,000) credits run out, OR
  - 30 days pass
- You can cancel before then

Click **"Launch cluster"**

---

### Step 7: Cluster Creation

**Wait 2-5 minutes** while Confluent creates your cluster.

You'll see:
```
Creating cluster...
Setting up infrastructure...
Initializing Kafka brokers...
```

**When done, you'll see:** ✅ "Cluster is ready"

---

## Phase 4: Create Kafka Topics (5 minutes)

### Step 1: Navigate to Topics

1. Click on your cluster name (e.g., `eventapp-prod`)
2. In the left sidebar, click **"Topics"**
3. Click **"Create topic"** or **"Add topic"**

---

### Step 2: Create Email Events Topic

**You'll be asked:**

| Field | What to Enter | Explanation |
|-------|---------------|-------------|
| **Topic name** | `email-events` | Name for email-related events |
| **Partitions** | `1` | Start with 1, increase if needed |
| **Retention time** | `7 days` or `168 hours` | How long to keep messages |
| **Retention size** | `Unlimited` | Leave as default |

**Answers:**
- **Topic name:** `email-events`
- **Partitions:** `1`
- **Retention time:** `7 days` (or `168 hours`)
- **Cleanup policy:** `delete` (default)
- **Compression:** `producer` (default)

Click **"Create with defaults"** or **"Create"**

---

### Step 3: Create Additional Topics

**Repeat for these topics:**

| Topic Name | Partitions | Retention | Purpose |
|------------|-----------|-----------|---------|
| `email-events` | 1 | 7 days | ✅ Created above |
| `ad-events` | 1 | 7 days | Advertising events |
| `waitlist-events` | 1 | 7 days | Waitlist notifications |
| `ticket-events` | 1 | 7 days | Ticket-related events |

**For each topic:**
1. Click **"Create topic"**
2. Enter topic name
3. Set partitions to `1`
4. Set retention to `7 days`
5. Click **"Create"**

---

## Phase 5: Get Connection Credentials (5 minutes)

### Step 1: Create API Key

1. In your cluster, click **"API Keys"** (left sidebar)
   - Or go to **"Cluster overview"** → **"API keys"** tab
2. Click **"Create key"** or **"Add key"**

---

### Step 2: API Key Scope

**Question:** "Select the scope for this API key"

**You'll see 2 options:**

| Option | What it Means | Our Choice |
|--------|---------------|------------|
| **Global access** | Can access all resources | ❌ Not recommended |
| **Granular access** | Limited to specific cluster | ✅ **Choose This** |

**What to Choose:** **Granular access** → Select your cluster (e.g., `eventapp-prod`)

**Why?** Better security - key only works for this cluster

Click **"Next"**

---

### Step 3: API Key Description

**Question:** "Description (optional)"

**What to Enter:** A descriptive name

**Examples:**
- `Railway Production`
- `EventApp Backend`
- `Main API Key`

**Our Answer:** `Railway Production`

Click **"Next"**

---

### Step 4: Save API Key Credentials

**⚠️ CRITICAL:** You'll see your credentials **ONLY ONCE**

**You'll see:**
```
API Key: QVL53FWSBYUNPDPV
API Secret: cfltd61uXdHFWFgEWetCNpo/r6+dd4M4nozizgc60k6ByZpp7dcGiRXfE85HjqRw
```

**What to Do:**

1. **Download the credentials** (click "Download and continue")
2. **Copy them immediately** to a safe place

**Save these values - you'll need them for Railway:**

```bash
# Save these for later!
KAFKA_API_KEY="QVL53FWSBYUNPDPV"
KAFKA_API_SECRET="cfltd61uXdHFWFgEWetCNpo/r6+dd4M4nozizgc60k6ByZpp7dcGiRXfE85HjqRw"
```

Click **"Done"** or **"I have saved my API key"**

---

### Step 5: Get Bootstrap Server URL

1. Go to **"Cluster overview"** or **"Cluster settings"**
2. Look for **"Bootstrap server"** or **"Endpoints"**
3. You'll see something like:

```
pkc-xxxxx.us-east-1.aws.confluent.cloud:9092
```

**Copy this URL** - you'll need it for Railway

**Save it:**
```bash
KAFKA_BOOTSTRAP_SERVERS_PROD=pkc-xxxxx.us-east-1.aws.confluent.cloud:9092
```

---

## Phase 6: Verify Setup (2 minutes)

### Check Your Configuration

You should now have:

- ✅ Confluent Cloud account
- ✅ Free credits ($400 or $1,000)
- ✅ Kafka cluster created (Basic tier)
- ✅ 4 topics created:
  - `email-events`
  - `ad-events`
  - `waitlist-events`
  - `ticket-events`
- ✅ API Key and Secret
- ✅ Bootstrap Server URL

---

## Phase 7: Configure Railway Environment Variables

Now add these to your Railway services:

### For `event-lifecycle-service`:

```bash
# Kafka Configuration (Confluent Cloud)
KAFKA_BOOTSTRAP_SERVERS_PROD=pkc-xxxxx.us-east-1.aws.confluent.cloud:9092
KAFKA_API_KEY=your-api-key-here
KAFKA_API_SECRET=your-api-secret-here
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
```

### For `real-time-service`:

```bash
# Copy from event-lifecycle-service
KAFKA_BOOTSTRAP_SERVERS=${{event-lifecycle-service.KAFKA_BOOTSTRAP_SERVERS_PROD}}
KAFKA_API_KEY=${{event-lifecycle-service.KAFKA_API_KEY}}
KAFKA_API_SECRET=${{event-lifecycle-service.KAFKA_API_SECRET}}
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
```

### For `email-consumer`:

```bash
# Copy all variables from event-lifecycle-service
# Use Railway's "Copy Variables" feature
```

### For `celery-worker`:

```bash
# Copy all variables from event-lifecycle-service
# Use Railway's "Copy Variables" feature
```

---

## Phase 8: Test Connection (Optional but Recommended)

### From Railway CLI:

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and link project
railway login
railway link

# Test connection to Kafka
railway run -s event-lifecycle-service python -c "
from kafka import KafkaProducer
import os

producer = KafkaProducer(
    bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS_PROD'),
    security_protocol='SASL_SSL',
    sasl_mechanism='PLAIN',
    sasl_plain_username=os.getenv('KAFKA_API_KEY'),
    sasl_plain_password=os.getenv('KAFKA_API_SECRET')
)
print('✅ Connected to Confluent Cloud Kafka!')
producer.close()
"
```

**Expected Output:** `✅ Connected to Confluent Cloud Kafka!`

---

## Complete Configuration Summary

### What You Created:

| Resource | Value | Where to Find |
|----------|-------|---------------|
| **Cluster Type** | Basic | Cluster overview |
| **Cloud Provider** | AWS | Cluster overview |
| **Region** | us-east-1 | Cluster overview |
| **Cluster Name** | eventapp-prod | Cluster list |
| **Bootstrap Server** | pkc-xxxxx.us-east-1.aws.confluent.cloud:9092 | Cluster settings |
| **API Key** | XXXXXXXXXXX | API Keys tab |
| **API Secret** | YYYYYYYYYYYY | API Keys tab (saved) |
| **Topics** | email-events, ad-events, waitlist-events, ticket-events | Topics tab |

### Environment Variables for Railway:

```bash
# Confluent Cloud Kafka Configuration
KAFKA_BOOTSTRAP_SERVERS_PROD=pkc-xxxxx.us-east-1.aws.confluent.cloud:9092
KAFKA_API_KEY=your-api-key
KAFKA_API_SECRET=your-api-secret
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN

# Note: SASL_MECHANISM is PLAIN for Confluent Cloud (not SCRAM-SHA-256)
```

---

## Monitoring and Management

### View Cluster Metrics:

1. Go to **Cluster overview**
2. You'll see:
   - **Throughput** (messages/sec)
   - **Storage** used
   - **Client connections**
   - **Credits remaining**

### View Topic Activity:

1. Click **Topics** → Select a topic
2. You'll see:
   - **Messages** count
   - **Partitions** status
   - **Consumers** connected
   - **Recent messages** (in "Messages" tab)

### Monitor Credits:

1. Click your profile (top right)
2. Select **Billing & payment**
3. You'll see:
   - **Credits remaining** (e.g., $350 of $400)
   - **Credits expiration date**
   - **Current usage**

---

## Common Questions During Setup

### Q: Do I need a credit card?

**A:** Eventually yes, but:
- You can **skip initially** (may require card later)
- You **won't be charged** during free trial
- You can **cancel** before credits run out

### Q: What happens after credits expire?

**A:**
- You'll be **billed** for usage
- **Standard tier** costs ~$50-150/month for your use case
- You can **delete cluster** before then to avoid charges

### Q: Can I use multiple regions?

**A:** Yes, but:
- Each cluster is **region-specific**
- Multi-region = **higher costs**
- Start with **one region** (closest to users)

### Q: How many partitions should I use?

**A:**
- **Start with 1** partition per topic
- **Increase later** if you need more throughput
- 1 partition = ~10 MB/s throughput (enough for most cases)

### Q: What's the retention time?

**A:**
- **7 days** is recommended for most use cases
- Messages **deleted after 7 days**
- Increase if you need longer history (costs more storage)

### Q: PLAIN vs SCRAM-SHA-256 for SASL?

**A:**
- **Confluent Cloud uses PLAIN**
- Don't confuse with Upstash (which used SCRAM-SHA-256)
- Use `SASL_MECHANISM=PLAIN` for Confluent

---

## Troubleshooting

### Issue: Can't create cluster

**Solution:**
- Verify email address
- Check if credits were applied
- Try different browser (Chrome recommended)
- Clear cache and cookies

### Issue: API key not working

**Solution:**
- Verify you copied **both** key and secret
- Check SASL_MECHANISM is `PLAIN` (not SCRAM-SHA-256)
- Ensure SECURITY_PROTOCOL is `SASL_SSL`
- API key takes 1-2 minutes to activate

### Issue: Can't see topics

**Solution:**
- Verify cluster is **fully created** (green checkmark)
- Refresh page
- Check you're viewing correct cluster

### Issue: Connection timeout

**Solution:**
- Check bootstrap server URL is correct
- Verify network/firewall allows port 9092
- Ensure Railway service has internet access

---

## Next Steps

1. ✅ Confluent Cloud cluster is ready
2. ✅ Topics created
3. ✅ API credentials obtained

**Now:**
1. Go back to [RAILWAY_QUICK_START.md](RAILWAY_QUICK_START.md)
2. Continue with **Step 2: Cloudflare R2 Setup**
3. Add Confluent credentials to Railway environment variables
4. Deploy and test!

---

## Quick Reference Card

**Save these credentials:**

```bash
# Confluent Cloud Configuration
CLUSTER_NAME=eventapp-prod
BOOTSTRAP_SERVER=pkc-xxxxx.us-east-1.aws.confluent.cloud:9092
API_KEY=your-api-key
API_SECRET=your-api-secret
SASL_MECHANISM=PLAIN
SECURITY_PROTOCOL=SASL_SSL

# Topics Created
- email-events
- ad-events
- waitlist-events
- ticket-events

# Credits
Amount: $400 (or $1,000 via AWS Marketplace)
Expires: 30 days from signup
```

---

## Cost Estimate

### During Free Trial (30 days):
- **Cost:** $0 (using credits)
- **Credits used:** ~$50-100/month for your use case
- **Remaining:** $300-350 (or $900-950 with AWS Marketplace)

### After Free Trial:
- **Basic Cluster:** ~$0.50-1.00/hour
- **Storage:** ~$0.10/GB-month
- **Throughput:** Included in Basic
- **Estimated Total:** $50-150/month

**You have 1-3 months free** depending on usage!

---

## Support

**Need help?**
- Confluent Docs: https://docs.confluent.io
- Community: https://forum.confluent.io
- Support: support@confluent.io (for paid plans)
- Stack Overflow: Tag `confluent-cloud`

---

## Congratulations! 🎉

You now have:
- ✅ Confluent Cloud account with free credits
- ✅ Production-ready Kafka cluster
- ✅ Topics configured
- ✅ API credentials ready

**Ready to deploy to Railway!** 🚀
