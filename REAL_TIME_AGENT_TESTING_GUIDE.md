# Real-Time Agent Testing Guide

This guide shows you how to see the Engagement Conductor Agent working in **real-time** with actual engagement data flowing through the system.

---

## 🎯 What Happens in Real-Time

When everything is running, here's the automatic flow:

```
1. Users join session → Signal Collector picks up activity
2. Engagement drops → Anomaly Detector finds it
3. Anomaly detected → Agent Orchestrator triggers
4. Agent decides intervention → WebSocket event sent to frontend
5. Decision appears in dashboard → You see it in UI in real-time!
```

---

## 🚀 Step 1: Start All Services

### Terminal 1: Start Infrastructure
```bash
cd c:\Users\User\Desktop\event-management-platform
docker-compose up postgres redis
```

Wait until you see:
```
✓ postgres ready
✓ redis ready
```

### Terminal 2: Start Agent Service
```bash
cd c:\Users\User\Desktop\event-management-platform\agent-service
python -m uvicorn app.main:app --reload --port 8003
```

Wait for:
```
✅ Connected to Redis
✅ Agent service ready
🚀 Starting Engagement Signal Collector...
📡 Subscribed to 4 channels
✅ Signal collector started
```

### Terminal 3: Start Real-Time Service
```bash
cd c:\Users\User\Desktop\event-management-platform\real-time-service
npm run dev
```

Wait for:
```
✓ Real-time service started on port 3002
```

### Terminal 4: Start Frontend
```bash
cd c:\Users\User\Desktop\event-management-platform\frontend\globalconnect
npm run dev
```

Wait for:
```
✓ Ready in http://localhost:3000
```

---

## 🎭 Step 2: Set Up a Live Session

### Option A: Use Existing Event Session

1. Navigate to: `http://localhost:3000/dashboard`
2. Click on any **existing event**
3. Click the **"🤖 AI Conductor"** tab
4. Note the **sessionId** in the browser console (will be like `event_evt_123_main`)

### Option B: Create New Event with Session

1. Go to: `http://localhost:3000/dashboard/events`
2. Create a new event
3. Create a session within that event
4. Note the session ID

---

## 📊 Step 3: Register Session with Agent

Before the agent can monitor a session, it needs to be registered:

### Method 1: Via API (Recommended)

```bash
# Register session with agent orchestrator
curl -X POST http://localhost:8003/api/v1/agent/sessions/register \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "event_evt_abc123_main",
    "event_id": "evt_abc123",
    "metadata": {
      "session_name": "Main Session",
      "organizer_id": "your_user_id"
    }
  }'
```

You should see:
```json
{
  "session_id": "event_evt_abc123_main",
  "event_id": "evt_abc123",
  "agent_mode": "MANUAL",
  "registered_at": "2026-01-05T12:00:00",
  "message": "Session registered with agent orchestrator"
}
```

### Method 2: Automatic Registration

The session will automatically register when the first anomaly is detected IF:
- The signal collector detects activity
- An anomaly occurs
- The agent orchestrator receives the event

---

## 🌊 Step 4: Generate Real Engagement Data

Now you need to create **actual user activity** in the session. The signal collector monitors these channels:

### A. Chat Messages

**Publish chat events to Redis:**

```bash
# Open Redis CLI
redis-cli

# Publish chat message
PUBLISH "platform.events.chat.message.v1" '{"sessionId":"event_evt_abc123_main","eventId":"evt_abc123","message":{"text":"Hello everyone!","userId":"user_1"}}'

# Publish more messages (simulate active chat)
PUBLISH "platform.events.chat.message.v1" '{"sessionId":"event_evt_abc123_main","eventId":"evt_abc123","message":{"text":"Great session!","userId":"user_2"}}'
PUBLISH "platform.events.chat.message.v1" '{"sessionId":"event_evt_abc123_main","eventId":"evt_abc123","message":{"text":"I agree!","userId":"user_3"}}'
```

### B. Poll Votes

```bash
# Publish poll votes
PUBLISH "platform.events.poll.vote.v1" '{"sessionId":"event_evt_abc123_main","eventId":"evt_abc123","pollId":"poll_1","userId":"user_1"}'
PUBLISH "platform.events.poll.vote.v1" '{"sessionId":"event_evt_abc123_main","eventId":"evt_abc123","pollId":"poll_1","userId":"user_2"}'
PUBLISH "platform.events.poll.vote.v1" '{"sessionId":"event_evt_abc123_main","eventId":"evt_abc123","pollId":"poll_1","userId":"user_3"}'
```

### C. User Activity (Joins/Leaves)

```bash
# User joins
PUBLISH "sync-events" '{"type":"user_join","sessionId":"event_evt_abc123_main","eventId":"evt_abc123","userId":"user_1"}'
PUBLISH "sync-events" '{"type":"user_join","sessionId":"event_evt_abc123_main","eventId":"evt_abc123","userId":"user_2"}'
PUBLISH "sync-events" '{"type":"user_join","sessionId":"event_evt_abc123_main","eventId":"evt_abc123","userId":"user_3"}'

# Reactions
PUBLISH "sync-events" '{"type":"reaction","sessionId":"event_evt_abc123_main","eventId":"evt_abc123"}'
```

---

## 📉 Step 5: Simulate an Engagement Drop

To trigger the agent, you need to create an **engagement drop**:

### Initial High Engagement (30 seconds)

```bash
# Burst of activity - creates baseline of "high engagement"
for i in {1..10}; do
  redis-cli PUBLISH "platform.events.chat.message.v1" "{\"sessionId\":\"event_evt_abc123_main\",\"eventId\":\"evt_abc123\",\"message\":{\"text\":\"Message $i\",\"userId\":\"user_$i\"}}"
  sleep 1
done
```

Wait **30 seconds** for baseline to establish.

### Sudden Drop (Stop all activity)

Now **stop sending messages** for 30-60 seconds.

The signal collector will notice:
- Chat messages per minute: **10+ → 0**
- Engagement score: **75+ → 40-50**
- Anomaly: **DROP detected**

---

## 👀 Step 6: Watch the Agent in Action

### In Agent Service Terminal (Terminal 2):

You'll see logs like this:

```
🔄 Calculating engagement for 1 sessions
✅ Engagement stored: event_ev... = 75.23 (HIGH)
📢 Anomaly published: event_ev... - DROP
🤖 Triggering Agent Orchestrator for event_ev... (DROP - HIGH)
[PERCEIVE] Session event_evt_abc123_main: engagement=45.2, users=3
[PERCEIVE] Anomaly detected: DROP
[DECIDE] Session event_evt_abc123_main: Selecting intervention
[DECIDE] Selected POLL with confidence 0.78
[APPROVAL] MANUAL mode - requires approval
[WAIT] Session event_evt_abc123_main: Waiting for approval
```

### In Frontend Dashboard:

1. **Engagement Chart** drops (green → yellow → red)
2. **Anomaly Alert** appears: ⚠️ "DROP anomaly detected"
3. **Agent Status** changes to "WAITING_APPROVAL"
4. **Decision Explainer** card appears showing:
   - Intervention type: "POLL"
   - Confidence: 78%
   - Reasoning: "Engagement dropped 35% in 2 minutes..."
   - Context and historical performance

### In Browser Console:

```
[EngagementDashboard] WebSocket initialized for session: event_evt_abc123_main
[Socket] Socket connected { socketId: "abc123" }
agent.status { status: "MONITORING" }
agent.decision { decision: { interventionType: "POLL", confidence: 0.78, ... } }
```

---

## ✅ Step 7: Approve the Intervention

### In the UI:

Click the **"Approve"** button on the decision card.

### What Happens:

1. API call to: `POST /api/v1/agent/sessions/{id}/decisions/{did}/approve`
2. Agent executes intervention
3. WebSocket event: `agent.intervention.executed`
4. UI updates: Decision card disappears, status returns to "MONITORING"
5. A poll is actually created in the database!

### In Agent Service Logs:

```
[ACT] Session event_evt_abc123_main: Executing POLL
[ACT] Intervention executed: intervention_abc123...
✅ Agent completed: event_ev... - Intervention: POLL (confidence: 0.78, status: LEARNING)
```

---

## 🔁 Step 8: Recovery (Optional)

After intervention is executed, simulate recovery:

```bash
# Burst of activity again (poll responses)
for i in {1..15}; do
  redis-cli PUBLISH "platform.events.poll.vote.v1" "{\"sessionId\":\"event_evt_abc123_main\",\"eventId\":\"evt_abc123\",\"pollId\":\"poll_1\",\"userId\":\"user_$i\"}"
  redis-cli PUBLISH "platform.events.chat.message.v1" "{\"sessionId\":\"event_evt_abc123_main\",\"eventId\":\"evt_abc123\",\"message\":{\"text\":\"Great poll!\",\"userId\":\"user_$i\"}}"
  sleep 1
done
```

You'll see engagement score climb back up: **45 → 65 → 78**

---

## 🎛️ Testing Different Agent Modes

### MANUAL Mode (Current Default)
- Agent suggests, waits for approval
- You click "Approve" or "Dismiss"

```bash
curl -X PUT http://localhost:8003/api/v1/agent/sessions/event_evt_abc123_main/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "MANUAL"}'
```

### SEMI_AUTO Mode
- High confidence (>75%) → Auto-executes
- Low confidence (<75%) → Waits for approval

```bash
curl -X PUT http://localhost:8003/api/v1/agent/sessions/event_evt_abc123_main/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "SEMI_AUTO"}'
```

### AUTO Mode
- All interventions auto-execute
- No approval needed

```bash
curl -X PUT http://localhost:8003/api/v1/agent/sessions/event_evt_abc123_main/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "AUTO"}'
```

---

## 📝 Monitoring & Debugging

### Check Agent Status

```bash
curl http://localhost:8003/api/v1/agent/sessions/event_evt_abc123_main/status
```

### Check Health

```bash
curl http://localhost:8003/health/detailed
```

### View Engagement Data

```bash
# In PostgreSQL
psql -h localhost -U postgres -d engagement_conductor
SELECT * FROM engagement_metrics ORDER BY time DESC LIMIT 10;
SELECT * FROM anomalies ORDER BY detected_at DESC LIMIT 5;
```

### Real-Time Redis Monitoring

```bash
# Monitor all published events
redis-cli MONITOR

# Subscribe to specific channels
redis-cli
SUBSCRIBE "engagement:update"
SUBSCRIBE "anomaly:detected"
SUBSCRIBE "session:event_evt_abc123_main:events"
```

---

## 🐛 Troubleshooting

### "Agent not running for session"

**Solution**: Register the session first
```bash
curl -X POST http://localhost:8003/api/v1/agent/sessions/register \
  -H "Content-Type: application/json" \
  -d '{"session_id":"event_evt_abc123_main","event_id":"evt_abc123"}'
```

### "No engagement data showing"

**Checks**:
1. ✓ Signal collector running? (Check agent-service logs for "📡 Subscribed to 4 channels")
2. ✓ Publishing to correct sessionId?
3. ✓ Redis channels match? (use `MONITOR` to debug)

### "WebSocket not connecting"

**Checks**:
1. ✓ Real-time service running on port 3002?
2. ✓ Browser console shows Socket connected?
3. ✓ Check CORS settings in real-time-service

### "No anomaly detected"

**Causes**:
- Need more baseline data (wait 30-60 seconds of activity)
- Drop not significant enough (need 20%+ drop)
- Signal collector calculation interval (default 5 seconds)

---

## 📊 Expected Timeline

Here's what you should see minute-by-minute:

**Minute 0-1**: Setup
- Start all services
- Register session
- Open dashboard

**Minute 1-2**: Baseline
- Send burst of messages
- Engagement climbs to 70-80
- Agent status: "MONITORING"

**Minute 2-3**: Drop
- Stop activity
- Engagement drops to 40-50
- Anomaly detected: ⚠️
- Agent suggests intervention

**Minute 3-4**: Decision
- Decision card appears in UI
- You approve or dismiss
- If approved: intervention executes

**Minute 4-5**: Recovery
- Send more activity
- Engagement climbs back
- Agent learns from outcome

---

## 🎯 Success Criteria

You've successfully tested the agent when you see:

- ✅ Engagement chart showing live data
- ✅ Anomaly alert appears when engagement drops
- ✅ Agent status updates in real-time
- ✅ Decision explainer shows AI reasoning
- ✅ Intervention executes when approved
- ✅ WebSocket events flowing (check console)
- ✅ Agent logs showing Perceive→Decide→Act→Learn cycle

---

## 🚀 Next Steps

Once you've seen it working in real-time:

1. **Test different scenarios**:
   - Spike anomaly (burst of activity)
   - Plateau anomaly (steady low engagement)
   - Different intervention types

2. **Test agent modes**:
   - Compare MANUAL vs SEMI_AUTO vs AUTO
   - Measure response times
   - Check success rates

3. **Performance testing**:
   - Multiple concurrent sessions
   - High message volume
   - Long-running sessions

4. **Production readiness**:
   - Review health check endpoints
   - Check rate limiting
   - Monitor LLM costs
   - Set up alerts

---

**You now have a fully operational, real-time AI Engagement Conductor!** 🎉

The agent will automatically monitor sessions, detect anomalies, suggest interventions, and help organizers keep attendees engaged - all in real-time!
