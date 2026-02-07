# Kafka Topics Auto-Creation Guide

This guide will help you create all required Kafka topics automatically.

## Prerequisites

- Python 3.7 or higher
- Internet connection (to reach Confluent Cloud)

## Step 1: Install Required Package

Open your terminal and run:

```bash
pip install confluent-kafka
```

**Note**: If you're using a virtual environment, activate it first:

```bash
# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

## Step 2: Run the Script

Navigate to your project root and run:

```bash
cd c:\Users\User\Desktop\event-management-platform
python create-kafka-topics.py
```

## What the Script Does

✅ **Automatically creates all missing topics**:
- `real-time.network.connections` ⚠️ **CRITICAL - Missing topic causing your issue**
- `oracle.predictions.networking-suggestions` ⚠️ **CRITICAL for suggestions**
- All other required topics (20 total)

✅ **Skips topics that already exist** (no duplicates)

✅ **Configures topics properly**:
- 3 partitions (good for moderate traffic)
- 7-day retention (configurable)
- Proper replication for high availability

✅ **Verifies critical topics** after creation

## Expected Output

```
================================================================================
🚀 Kafka Topics Auto-Creation Script
================================================================================

📡 Connecting to Confluent Cloud...
✅ Connected successfully to pkc-oxqxx9.us-east-1.aws.confluent.cloud:9092

🔍 Fetching existing topics...
✅ Found 12 existing topics

📋 Analyzing topics...
--------------------------------------------------------------------------------
⏭️  SKIP: platform.events.chat.message.v1 (already exists)
➕ CREATE: real-time.network.connections
   └─ Network connection events to trigger AI suggestions
➕ CREATE: oracle.predictions.networking-suggestions
   └─ AI-powered networking suggestions (CRITICAL for suggestions feature)
...
--------------------------------------------------------------------------------

📊 Summary:
   • Total topics defined: 20
   • Already exist (skipped): 12
   • Will be created: 8

🔨 Creating topics...
--------------------------------------------------------------------------------
✅ Created: real-time.network.connections
✅ Created: oracle.predictions.networking-suggestions
...
--------------------------------------------------------------------------------

================================================================================
🎉 Topic Creation Complete!
================================================================================
✅ Successfully created: 8 topics

🔐 Verifying critical topics for suggestions feature...
✅ All critical topics exist!
   • real-time.network.connections
   • oracle.predictions.networking-suggestions

🚀 Your suggestions feature should now work!

================================================================================
📝 Next Steps:
   1. Verify topics in Confluent Cloud Console
   2. Check ACL permissions for your API key
   3. Test the Connect button in your app
================================================================================
```

## Troubleshooting

### Error: "confluent-kafka not found"

**Solution**: Install the package:
```bash
pip install confluent-kafka
```

### Error: "Failed to connect to Kafka"

**Possible causes**:
1. Wrong credentials (check `.env.production`)
2. Network/firewall blocking Confluent Cloud
3. API key revoked or expired

**Solution**: Verify credentials in `real-time-service/.env.production`

### Error: "TOPIC_AUTHORIZATION_FAILED"

**Cause**: Your API key doesn't have CREATE permission on topics.

**Solution**:
1. Go to Confluent Cloud Console
2. Navigate to **API Keys** → Select your key `QVL53FWSBYUNPDPV`
3. Add **CREATE** permission for topic pattern `*` or specific topic prefixes

### Topics created but Connect button still fails

**Solution**: Check ACL permissions for WRITE access:
1. Go to Confluent Cloud → **Topics** → `real-time.network.connections`
2. Click **Access control (ACLs)**
3. Ensure your API key has **WRITE** permission

## Verify Topics in Confluent Cloud

After running the script:

1. Go to https://confluent.cloud
2. Navigate to your cluster → **Topics**
3. Search for `real-time.network.connections`
4. You should see it in the list with 3 partitions

## Test Your Suggestions Feature

Once topics are created:

1. Redeploy `real-time-service` (or restart if running locally)
2. Redeploy `oracle-ai-service` (or restart if running locally)
3. Go to your app → **Networking** → **Recommended** tab
4. Click **Connect** on a recommendation
5. Check oracle-ai-service logs - you should see:
   ```
   [SUGGESTIONS] Processing new connection between user1 and user2...
   [SUGGESTIONS] Generated suggestion for user1 → user3
   ```
6. Check SuggestionsBell - a new notification should appear!

## Manual Creation (Alternative)

If the script doesn't work, you can create topics manually via Confluent Cloud Console:

1. Go to your cluster → **Topics** → **Create topic**
2. Enter topic name: `real-time.network.connections`
3. Set partitions: `3`
4. Set retention: `7 days`
5. Click **Create**

Repeat for `oracle.predictions.networking-suggestions` and other missing topics.

## Support

If you encounter issues:
- Check Confluent Cloud service status
- Verify API key has required permissions (READ, WRITE, CREATE)
- Check service logs for detailed error messages
