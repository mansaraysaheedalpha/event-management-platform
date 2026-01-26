# Sponsor Messaging System - Setup & Deployment Guide

## 🎯 Overview

Production-grade sponsor email campaign system built using Google engineering best practices:

- ✅ **Async Processing**: Kafka-based queue for scalable batch sending
- ✅ **Rate Limiting**: Respects Resend API limits (10 req/sec)
- ✅ **Template Personalization**: Jinja2 templates with {{name}}, {{company}}, etc.
- ✅ **Delivery Tracking**: Per-recipient status, opens, clicks
- ✅ **Audience Filtering**: Hot/warm/cold leads, custom filters
- ✅ **Retry Logic**: Automatic retry for failed sends (max 3 attempts)
- ✅ **Error Handling**: Comprehensive logging and error tracking

---

## 📋 What Was Built

### Backend (Python/FastAPI)

#### 1. **Database Models**
- `app/models/sponsor_campaign.py` - Campaign metadata and stats
- `app/models/campaign_delivery.py` - Per-lead delivery tracking
- `app/models/sponsor.py` - Added campaigns relationship

#### 2. **Database Migration**
- `alembic/versions/sp002_create_sponsor_campaign_tables.py`
- Creates `sponsor_campaigns` and `campaign_deliveries` tables
- Includes indexes for performance

#### 3. **API Endpoints**
- `app/api/v1/endpoints/sponsor_campaigns.py`
  - `POST /sponsors/{sponsor_id}/campaigns` - Create & send campaign
  - `GET /sponsors/{sponsor_id}/campaigns` - List campaigns
  - `GET /sponsors/{sponsor_id}/campaigns/{campaign_id}` - Get campaign details
  - `GET /sponsors/{sponsor_id}/campaigns/{campaign_id}/stats` - Campaign analytics
  - `GET /sponsors/{sponsor_id}/campaigns/{campaign_id}/deliveries` - Delivery status
  - `DELETE /sponsors/{sponsor_id}/campaigns/{campaign_id}` - Delete draft
  - `GET /campaigns/track/open/{delivery_id}.png` - Open tracking pixel
  - `GET /campaigns/track/click/{delivery_id}` - Click tracking

#### 4. **CRUD Operations**
- `app/crud/crud_sponsor_campaign.py` - Campaign CRUD with audience filtering
- `app/crud/crud_campaign_delivery.py` - Delivery tracking CRUD

#### 5. **Pydantic Schemas**
- `app/schemas/sponsor_campaign.py` - Request/response validation
- Includes template variable validation
- Sanitization to prevent injection attacks

#### 6. **Email Worker (Kafka Consumer)**
- `app/workers/campaign_email_worker.py`
- Processes campaigns asynchronously
- Batch processing with rate limiting
- Jinja2 template personalization
- Resend API integration
- Delivery status tracking

### Frontend (Next.js/React)

#### 1. **Messages Tab**
- `src/app/(sponsor)/sponsor/messages/page.tsx`
- Updated to use real backend API (was mockup)
- Shows real-time recipient counts
- Error handling with toast notifications

---

## 🚀 Deployment Steps

### Step 1: Run Database Migration

```bash
cd event-lifecycle-service

# Run the migration
alembic upgrade head

# Verify tables were created
psql -d your_database -c "\dt sponsor_campaigns"
psql -d your_database -c "\dt campaign_deliveries"
```

Expected output:
```
                  List of relations
 Schema |        Name        | Type  |  Owner
--------+--------------------+-------+----------
 public | sponsor_campaigns  | table | postgres
 public | campaign_deliveries| table | postgres
```

### Step 2: Configure Environment Variables

Add to `.env` in `event-lifecycle-service/`:

```bash
# Resend Email API (Required)
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
RESEND_FROM_DOMAIN=eventdynamics.io  # or your verified domain

# Kafka (Required for async processing)
KAFKA_BOOTSTRAP_SERVERS=your-kafka-server:9092
KAFKA_API_KEY=your_confluent_key      # If using Confluent Cloud
KAFKA_API_SECRET=your_confluent_secret
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN

# App URL (for tracking links)
NEXT_PUBLIC_APP_URL=https://eventdynamics.io
```

### Step 3: Install Python Dependencies

```bash
cd event-lifecycle-service

# Install Jinja2 for templates
pip install jinja2

# Dependencies should already be installed:
# - resend (email API)
# - kafka-python (Kafka consumer)
# - sqlalchemy (ORM)
```

### Step 4: Start the Email Worker

**Option A: Development (foreground)**
```bash
cd event-lifecycle-service
python -m app.workers.campaign_email_worker
```

**Option B: Production (systemd service)**

Create `/etc/systemd/system/campaign-worker.service`:

```ini
[Unit]
Description=Sponsor Campaign Email Worker
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/event-lifecycle-service
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python -m app.workers.campaign_email_worker
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable campaign-worker
sudo systemctl start campaign-worker
sudo systemctl status campaign-worker
```

**Option C: Production (Docker)**

Add to `docker-compose.yml`:

```yaml
campaign-worker:
  build: ./event-lifecycle-service
  command: python -m app.workers.campaign_email_worker
  environment:
    - RESEND_API_KEY=${RESEND_API_KEY}
    - KAFKA_BOOTSTRAP_SERVERS=${KAFKA_BOOTSTRAP_SERVERS}
    - SQLALCHEMY_DATABASE_URI=${DATABASE_URL}
  depends_on:
    - postgres
    - kafka
  restart: unless-stopped
```

### Step 5: Verify Setup

#### Test 1: Check API Endpoints

```bash
# Health check - list campaigns (should return empty array)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/sponsors/YOUR_SPONSOR_ID/campaigns
```

#### Test 2: Create Test Campaign

```bash
curl -X POST \
  http://localhost:8000/api/v1/sponsors/YOUR_SPONSOR_ID/campaigns \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Campaign",
    "subject": "Hello {{name}}!",
    "message_body": "Hi {{name}},\n\nThis is a test message.\n\nBest regards",
    "audience_type": "all",
    "metadata": {}
  }'
```

Expected response:
```json
{
  "id": "spcmpn_abc123",
  "status": "queued",
  "total_recipients": 5,
  ...
}
```

#### Test 3: Check Worker Logs

```bash
# If running with systemd
sudo journalctl -u campaign-worker -f

# If running manually
tail -f campaign_worker.log
```

Expected output:
```
[2026-01-26 ...] INFO Starting campaign email worker...
[2026-01-26 ...] INFO Kafka consumer connected successfully
[2026-01-26 ...] INFO Listening for campaigns...
[2026-01-26 ...] INFO Received event: campaign.send
[2026-01-26 ...] INFO Processing campaign: spcmpn_abc123
[2026-01-26 ...] INFO Campaign spcmpn_abc123: Found 5 recipients
[2026-01-26 ...] INFO Processing batch 1 (5 emails)
[2026-01-26 ...] INFO Campaign spcmpn_abc123 complete: 5 sent, 0 failed
```

---

## 📊 Usage Guide

### For Sponsors (via Frontend)

1. **Navigate to Messages tab** in sponsor dashboard
2. **Select audience**:
   - All Leads
   - Hot Leads Only
   - Warm Leads
   - New (Not Contacted)
   - Previously Contacted
3. **Compose message**:
   - Write subject line
   - Write message body (supports {{name}}, {{company}}, etc.)
   - Or use quick templates
4. **Click "Send Now"**
5. **Track progress**:
   - View in campaign list
   - Check delivery status
   - See open/click rates

### API Usage (Programmatic)

#### Create Campaign

```python
import requests

response = requests.post(
    f"{API_BASE}/sponsors/{sponsor_id}/campaigns",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "name": "Monthly Newsletter",
        "subject": "Updates from {{company}}",
        "message_body": "Hello {{name}},\n\nWe wanted to share...",
        "audience_type": "hot",  # hot, warm, cold, all, new, contacted
    }
)
campaign = response.json()
print(f"Campaign queued: {campaign['id']}")
```

#### Get Campaign Stats

```python
response = requests.get(
    f"{API_BASE}/sponsors/{sponsor_id}/campaigns/{campaign_id}/stats",
    headers={"Authorization": f"Bearer {token}"}
)
stats = response.json()
print(f"Open rate: {stats['open_rate']}%")
print(f"Click rate: {stats['click_rate']}%")
```

---

## 🔧 Configuration

### Rate Limiting

Edit `app/workers/campaign_email_worker.py`:

```python
# Resend allows 10 req/sec
BATCH_SIZE = 50  # Emails per batch
BATCH_DELAY_MS = 100  # Delay between batches (100ms = 10 batches/sec)
```

### Template Variables

Available in all campaigns:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{name}}` | Full name | "John Doe" |
| `{{first_name}}` | First name only | "John" |
| `{{last_name}}` | Last name only | "Doe" |
| `{{company}}` | Company name | "Acme Corp" |
| `{{title}}` | Job title | "CTO" |
| `{{email}}` | Email address | "john@acme.com" |

### Audience Filtering

| Type | Description | SQL Filter |
|------|-------------|------------|
| `all` | All leads with email | `user_email IS NOT NULL` |
| `hot` | High intent leads | `intent_level = 'hot'` |
| `warm` | Medium intent | `intent_level = 'warm'` |
| `cold` | Low intent | `intent_level = 'cold'` |
| `new` | Never contacted | `follow_up_status = 'new'` |
| `contacted` | Previously contacted | `follow_up_status != 'new'` |
| `custom` | Custom filter | Use `audience_filter` JSON |

### Custom Filters Example

```json
{
  "audience_type": "custom",
  "audience_filter": {
    "intent_score_min": 50,
    "intent_score_max": 100,
    "tags": ["enterprise", "decision_maker"]
  }
}
```

---

## 🐛 Troubleshooting

### Issue: Campaigns stuck in "queued" status

**Cause**: Worker not running or Kafka not connected

**Fix**:
```bash
# Check worker status
sudo systemctl status campaign-worker

# Check worker logs
sudo journalctl -u campaign-worker -n 50

# Restart worker
sudo systemctl restart campaign-worker
```

### Issue: All emails fail with "Resend API error"

**Cause**: Invalid or missing RESEND_API_KEY

**Fix**:
1. Get API key from https://resend.com/api-keys
2. Add to `.env`: `RESEND_API_KEY=re_...`
3. Restart worker

### Issue: "Domain not verified" error

**Cause**: Sending from unverified domain

**Fix**:
1. Verify domain in Resend dashboard
2. Add DNS records (SPF, DKIM, DMARC)
3. Or use `noreply@resend.dev` for testing

### Issue: Template variables not replaced

**Cause**: Lead data missing (e.g., user_name is NULL)

**Fix**: Variables fallback to defaults:
- `{{name}}` → "there" if NULL
- `{{company}}` → "" if NULL

Check lead data:
```sql
SELECT user_name, user_email, user_company
FROM sponsor_leads
WHERE sponsor_id = 'YOUR_SPONSOR_ID';
```

---

## 📈 Performance & Scaling

### Current Limits

- **Resend Free Tier**: 100 emails/day, 3000/month
- **Resend Pro**: $20/month = unlimited emails
- **Batch Processing**: ~500 emails/minute (with 100ms delay)
- **Kafka**: Can handle millions of events/sec

### Scaling Recommendations

1. **For > 10K recipients**:
   - Upgrade to Resend Pro
   - Deploy multiple worker instances
   - Increase `BATCH_SIZE` to 100

2. **For > 100K recipients**:
   - Use Confluent Cloud Kafka (auto-scaling)
   - Deploy workers as Kubernetes pods
   - Consider SendGrid or AWS SES (higher limits)

3. **Database Optimization**:
   - Already has indexes on key columns
   - Consider partitioning `campaign_deliveries` by month
   - Archive old campaigns after 90 days

---

## 🔐 Security

### Input Sanitization

All user input is sanitized:
- Subject lines: No line breaks, limited whitespace
- Message body: Template variable validation
- SQL injection: Prevented by SQLAlchemy ORM
- XSS: HTML is not rendered in plain text emails

### Permissions

API endpoints check:
1. User is active sponsor representative
2. User has `can_send_messages` permission
3. Sponsor tier has messaging enabled (`can_send_messages` flag)

### Rate Limiting

API endpoints have rate limits:
- Create campaign: 10/minute
- List campaigns: 30/minute
- Get stats: 30/minute

---

## 📝 Database Schema

### sponsor_campaigns

| Column | Type | Description |
|--------|------|-------------|
| id | string | Primary key |
| sponsor_id | string | FK to sponsors |
| event_id | string | FK to events |
| name | string | Internal campaign name |
| subject | string | Email subject |
| message_body | text | Email body with {{vars}} |
| audience_type | string | all, hot, warm, etc. |
| status | string | draft, queued, sending, sent, failed |
| total_recipients | int | Total leads targeted |
| sent_count | int | Successfully sent |
| opened_count | int | Emails opened |
| clicked_count | int | Links clicked |

### campaign_deliveries

| Column | Type | Description |
|--------|------|-------------|
| id | string | Primary key |
| campaign_id | string | FK to campaigns |
| lead_id | string | FK to leads |
| recipient_email | string | Recipient email |
| status | string | pending, sent, delivered, failed |
| provider_message_id | string | Resend message ID |
| opened_at | datetime | First open timestamp |
| first_click_at | datetime | First click timestamp |

---

## ✅ Production Checklist

- [ ] Database migration completed
- [ ] `.env` variables configured (Resend, Kafka)
- [ ] Resend domain verified (or using resend.dev)
- [ ] Kafka topic created: `sponsor.campaigns.v1`
- [ ] Email worker running and connected
- [ ] Test campaign sent successfully
- [ ] Tracking pixel working (check worker logs)
- [ ] Monitoring/alerts configured
- [ ] Sponsor tier messaging permissions set
- [ ] Frontend Messages tab tested

---

## 🎓 Architecture Diagram

```
┌─────────────┐
│   Frontend  │
│ Messages Tab│
└──────┬──────┘
       │ POST /campaigns
       ▼
┌──────────────────┐
│  FastAPI Backend │
│  (Event Lifecycle│
│    Service)      │
└────────┬─────────┘
         │ Publish event
         ▼
    ┌────────┐
    │ Kafka  │
    │ Topic  │
    └────┬───┘
         │ Subscribe
         ▼
┌─────────────────────┐
│  Email Worker       │
│  (Kafka Consumer)   │
│  - Batch processing │
│  - Rate limiting    │
│  - Template render  │
└──────────┬──────────┘
           │ Send email
           ▼
      ┌─────────┐
      │ Resend  │
      │   API   │
      └─────────┘
```

---

## 🆘 Support

For issues or questions:
1. Check worker logs: `tail -f campaign_worker.log`
2. Check API logs: FastAPI console output
3. Check database: Query `sponsor_campaigns` and `campaign_deliveries`
4. Review this guide's Troubleshooting section

Built with ❤️ using Google-grade engineering practices.
