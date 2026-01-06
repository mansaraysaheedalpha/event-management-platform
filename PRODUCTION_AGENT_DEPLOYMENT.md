# Production Agent Deployment Guide

**Status**: ✅ **PRODUCTION READY**

The Engagement Conductor Agent is now fully production-ready and works **automatically** with zero manual intervention required.

---

## 🎯 How It Works in Production

When you deploy to production, the agent operates completely automatically:

### 1. **Automatic Session Monitoring**
- ✅ **No manual registration needed**
- When users join a session and start chatting/voting, the signal collector automatically picks up activity
- First anomaly detection automatically registers the session with the agent
- Agent starts monitoring immediately

### 2. **Smart Agent Modes** (Per Event)

#### **SEMI_AUTO** (Default - Recommended for Production)
- ✅ **High confidence (>75%)**: Auto-executes immediately
- ✅ **Low confidence (<75%)**: Waits for organizer IF they're online
- ✅ **Works without organizer**: Doesn't block if nobody approves
- Perfect balance of automation and safety

#### **AUTO** (Fully Autonomous)
- ✅ **All interventions auto-execute**
- ✅ **Zero human intervention needed**
- ✅ **Agent handles everything**
- Best for events where organizers aren't actively monitoring

#### **MANUAL** (Least Automated)
- ⚠️ **All interventions wait for approval**
- ⚠️ **May miss opportunities if organizer offline**
- Only recommended if organizer is actively watching dashboard

### 3. **Real-Time Data Flow** (100% Automatic)

```
User Activity (Chat/Polls/Reactions)
    ↓ (Captured via WebSocket & Redis)
Signal Collector
    ↓ (Calculates every 5 seconds)
Engagement Score
    ↓ (Monitors for drops/spikes)
Anomaly Detection
    ↓ (Automatic when detected)
Agent Auto-Registers Session
    ↓ (Runs full AI cycle)
Agent Decides Intervention
    ↓ (Based on mode)
Execute or Wait
    ↓ (Publishes to Redis)
Real-Time Service
    ↓ (Forwards via WebSocket)
Frontend Updates
    ↓
Organizer Sees It (Optional - for awareness only)
```

**No manual steps required!**

---

## 🚀 Production Deployment Steps

### Step 1: Run Database Migration

```bash
# Connect to your production database
psql -h your-prod-db.com -U postgres -d engagement_conductor

# Run migration to add event agent settings table
\i agent-service/app/db/migrations/add_event_agent_settings.sql
```

This creates the `event_agent_settings` table where agent configuration is stored per event.

### Step 2: Set Environment Variables

**Agent Service** (`agent-service/.env`):
```bash
# Production Database
DATABASE_URL=postgresql://user:pass@your-db.com:5432/engagement_conductor

# Redis (for real-time events)
REDIS_URL=redis://your-redis.com:6379

# Claude AI API Key (for content generation)
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Optional: LangSmith for monitoring agent decisions
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=engagement-conductor-prod

# Rate limiting (production values)
MAX_REQUESTS_PER_MINUTE=60
MAX_LLM_COST_PER_HOUR=20.00
MAX_LLM_COST_PER_DAY=100.00
```

**Real-Time Service** (`real-time-service/.env`):
```bash
DATABASE_URL=postgresql://user:pass@your-db.com:5432/event_management
REDIS_URL=redis://your-redis.com:6379
JWT_SECRET=your-production-secret-here
NODE_ENV=production
```

**Frontend** (`.env.production`):
```bash
NEXT_PUBLIC_SOCKET_URL=https://your-realtime-service.com
NEXT_PUBLIC_AGENT_SERVICE_URL=https://your-agent-service.com
```

### Step 3: Deploy Services

```bash
# Deploy with Docker Compose (recommended)
docker-compose -f docker-compose.prod.yml up -d

# Or deploy individually to your cloud provider
# - Agent service on port 8003
# - Real-time service on port 3002
# - Frontend on port 3000
```

### Step 4: Verify Deployment

```bash
# Check agent service health
curl https://your-agent-service.com/health/detailed

# Should return:
{
  "status": "healthy",
  "redis": "connected",
  "database": "connected",
  "signal_collector": "running",
  "agent_orchestrator": "ready"
}

# Check real-time service
curl https://your-realtime-service.com/health

# Should return:
{
  "status": "ok"
}
```

---

## 🎮 Configuring Agent Per Event

### Option 1: Via Database (For Existing Events)

```sql
-- Set event to SEMI_AUTO mode (recommended)
INSERT INTO event_agent_settings (event_id, agent_enabled, agent_mode)
VALUES ('evt_abc123', TRUE, 'SEMI_AUTO')
ON CONFLICT (event_id) DO UPDATE SET agent_mode = 'SEMI_AUTO';

-- Set event to AUTO mode (fully autonomous)
INSERT INTO event_agent_settings (event_id, agent_enabled, agent_mode)
VALUES ('evt_xyz789', TRUE, 'AUTO')
ON CONFLICT (event_id) DO UPDATE SET agent_mode = 'AUTO';

-- Disable agent for specific event
INSERT INTO event_agent_settings (event_id, agent_enabled, agent_mode)
VALUES ('evt_disabled', FALSE, 'MANUAL')
ON CONFLICT (event_id) DO UPDATE SET agent_enabled = FALSE;
```

### Option 2: Via API (For New Events)

Add this to your event creation flow in `event-lifecycle-service`:

```typescript
// When creating a new event, also create agent settings
await fetch('https://your-agent-service.com/api/v1/events/settings', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    event_id: newEvent.id,
    agent_enabled: true,
    agent_mode: 'SEMI_AUTO', // or let organizer choose
    auto_approve_threshold: 0.75,
    max_interventions_per_hour: 3
  })
});
```

### Option 3: Add to Event Creation UI (Future Enhancement)

In your event creation form, add:
```tsx
<select name="agentMode">
  <option value="SEMI_AUTO">Smart Auto (Recommended)</option>
  <option value="AUTO">Fully Automatic</option>
  <option value="MANUAL">Manual Approval Only</option>
</select>
```

---

## 📊 What Happens in Production

### Scenario: Event Goes Live

**T+0:00** - Event starts
- Attendees join session
- Signal collector automatically picks up activity
- Engagement score: 75 (HIGH)

**T+0:15** - Active chat, polls
- 20 chat messages/min
- 60% poll participation
- Engagement score: 82 (HIGH)
- ✅ Agent monitors, no action needed

**T+0:25** - Engagement drops
- Chat slows to 2 messages/min
- Poll participation drops to 15%
- **Anomaly detected: DROP (severity: HIGH)**
- **Agent auto-registers session** (first time)
- **Agent mode: SEMI_AUTO** (from event settings)

**T+0:25:05** - Agent decides
- **Intervention: POLL**
- **Confidence: 82%** (>75% threshold)
- **Action: AUTO-EXECUTE** ✅
- Poll created automatically
- WebSocket event sent to frontend

**T+0:25:10** - Organizer (if watching dashboard)
- Sees notification: "AI created a poll to re-engage attendees"
- Can see reasoning and confidence
- **No action required** - already executed

**T+0:26** - Recovery
- Attendees vote on poll
- Chat picks up again
- Engagement climbs to 78
- ✅ Success recorded, agent learns

**T+0:35** - Another drop
- Different anomaly pattern
- **Agent suggests: PROMPT**
- **Confidence: 68%** (<75% threshold)
- **Action: WAIT FOR APPROVAL** (if organizer online)
- **Timeout: 60 seconds**
- **If no approval: SKIP** (doesn't block)

**All of this happens automatically!**

---

## 🛡️ Production Safety Features

### 1. **Rate Limiting**
- Max 60 requests/min to prevent abuse
- LLM cost tracking: $20/hour, $100/day limits
- Automatic throttling when limits approached

### 2. **Error Handling**
- Structured error responses
- Automatic retry with exponential backoff
- Falls back to Phase 3 rule-based system if AI fails

### 3. **Monitoring**
- Health check endpoints for orchestration
- Metrics endpoint shows agent performance
- LangSmith tracing for debugging decisions

### 4. **Graceful Degradation**
- If Redis fails: Agent continues with polling
- If DB fails: Uses cached settings
- If AI API fails: Falls back to rule-based

---

## 📈 Monitoring in Production

### Health Checks (For Load Balancer)

```bash
# Liveness probe (is service alive?)
GET /health

# Readiness probe (can it handle requests?)
GET /health/ready

# Detailed health (all components)
GET /health/detailed
```

### Performance Metrics

```bash
# Agent performance metrics
GET /metrics

Response:
{
  "total_interventions": 245,
  "successful_interventions": 189,
  "success_rate": 0.77,
  "average_confidence": 0.81,
  "average_response_time_ms": 245,
  "llm_costs": {
    "hourly": 2.45,
    "daily": 18.30,
    "hourly_limit": 20.00,
    "daily_limit": 100.00
  },
  "active_sessions": 12,
  "agent_modes": {
    "MANUAL": 2,
    "SEMI_AUTO": 8,
    "AUTO": 2
  }
}
```

### Log Monitoring

Set up alerts for:
```bash
# Critical errors
grep "❌" agent-service.log

# Failed interventions
grep "Intervention execution failed" agent-service.log

# Rate limit warnings
grep "Rate limit" agent-service.log

# Cost warnings
grep "LLM cost approaching" agent-service.log
```

---

## 🎓 Recommendations for Production

### 1. **Start with SEMI_AUTO**
- Best balance of automation and control
- High-confidence interventions execute immediately
- Low-confidence ones wait (but don't block)
- Organizers can override if watching

### 2. **Monitor First Week**
- Watch success rates
- Review agent decisions in LangSmith
- Adjust thresholds if needed
- Gather feedback from organizers

### 3. **Gradually Increase Automation**
- Week 1: SEMI_AUTO (75% threshold)
- Week 2: SEMI_AUTO (70% threshold) if success rate >75%
- Week 3+: Consider AUTO for smaller events

### 4. **Set Up Notifications**
- Email organizers on anomalies (optional)
- Slack/Discord alerts for critical drops
- Daily summary reports

---

## ✅ Production Readiness Checklist

Before deploying:

- [ ] ✅ Database migration run (`add_event_agent_settings.sql`)
- [ ] ✅ Environment variables configured
- [ ] ✅ Agent service deployed and healthy
- [ ] ✅ Real-time service deployed and healthy
- [ ] ✅ Frontend deployed with correct env vars
- [ ] ✅ Redis accessible from both services
- [ ] ✅ PostgreSQL accessible from both services
- [ ] ✅ CORS configured for production domains
- [ ] ✅ SSL certificates installed
- [ ] ✅ Health check endpoints responding
- [ ] ✅ Monitoring/alerting configured
- [ ] ✅ LLM API key set with billing limits
- [ ] ✅ Default agent mode set to SEMI_AUTO
- [ ] ✅ Test with 1-2 events before full rollout
- [ ] ✅ Organizers briefed on agent features

---

## 🌟 What Organizers Will Experience

### With Agent Enabled (SEMI_AUTO):

1. **Event starts normally** - nothing different
2. **Engagement naturally fluctuates** - expected
3. **When engagement drops**:
   - Organizer gets subtle notification (optional)
   - Agent already handled it (poll/prompt created)
   - Engagement recovers
   - Organizer sees: "AI helped re-engage 23 attendees"
4. **Dashboard shows**:
   - Real-time engagement chart
   - Agent activity feed
   - Intervention history
   - Success metrics

**It just works - like magic!** ✨

---

## 🚨 Important Notes

### Data Privacy
- Agent decisions are logged for learning
- No personal user data sent to AI
- Only aggregate metrics (scores, counts)
- Compliant with GDPR/privacy regulations

### Cost Management
- Default limits: $20/hour, $100/day
- Approximately $0.05-0.15 per intervention
- ~200-500 interventions per day at limit
- Scales with usage

### User Experience
- Interventions appear organic
- Users don't know it's AI
- Maintains platform feel
- No disruption to natural flow

---

## 📞 Support & Troubleshooting

If issues arise in production:

1. **Check health endpoints** - Are services running?
2. **Review logs** - What errors are appearing?
3. **Check Redis** - Is pub/sub working?
4. **Verify database** - Are metrics being saved?
5. **Test WebSocket** - Can frontend connect?
6. **Review agent mode** - Is it set correctly for event?

**The system is designed to gracefully degrade** - if anything fails, it falls back to safe defaults and doesn't break the event experience.

---

**Status**: ✅ **READY FOR PRODUCTION DEPLOYMENT**

The agent will now work automatically with real user interactions, no manual intervention required!
