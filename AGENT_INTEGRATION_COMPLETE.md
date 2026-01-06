# Engagement Conductor Agent - Full Integration Complete

**Status**: ✅ All Phases (5 & 6) are now fully integrated with real-time data flow from backend → frontend

---

## Overview

The Engagement Conductor Agent is now fully operational with complete real-time connectivity. All components from Phase 5 (Full Agent Loop) and Phase 6 (Polish, Testing & Demo) are integrated into the UI and connected to the backend services.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                           FRONTEND                                   │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  EngagementDashboard.tsx                                        │ │
│  │  ├─ AgentModeToggle (Manual/Semi-Auto/Auto)                   │ │
│  │  ├─ AgentStatus (Monitoring/Waiting/Intervening)              │ │
│  │  ├─ DecisionExplainer (Shows reasoning)                       │ │
│  │  ├─ OnboardingTour (First-time user guide)                    │ │
│  │  └─ Demo Mode & Export Utilities                              │ │
│  │                                                                 │ │
│  │  Hooks:                                                         │ │
│  │  ├─ useAgentState (Agent mode, status, decisions) ────┐       │ │
│  │  ├─ useEngagementStream (Real-time engagement data)   │       │ │
│  │  └─ useInterventions (Intervention history)           │       │ │
│  └────────────────────────────────────────────────────────┼───────┘ │
│                                                            │         │
│  WebSocket Client (socket.io-client)                      │         │
│  ├─ Connects to: ws://localhost:3002/events               │         │
│  ├─ Subscribes to: agent:subscribe {sessionId}            │         │
│  └─ Listens for:                                           │         │
│      • agent.status                                        │         │
│      • agent.decision                                      │         │
│      • agent.intervention.executed                         │         │
└────────────────────────────────────────────────────────────┼─────────┘
                                                             │
                                                     WebSocket
                                                             │
┌────────────────────────────────────────────────────────────┼─────────┐
│                      REAL-TIME SERVICE                     │         │
│                                                            │         │
│  EngagementConductorGateway                                │         │
│  ├─ Listens to WebSocket subscriptions                    │         │
│  ├─ Subscribes to Redis channels:                         │         │
│  │   session:{sessionId}:events                           │         │
│  └─ Forwards events to WebSocket clients                  │         │
│                                                            │         │
│  Redis Subscriber ─────────────────────────────────────────┘         │
└──────────────────────────────────────────────────────────────────────┘
                                ▲
                                │ Redis Pub/Sub
                                │
┌───────────────────────────────┼───────────────────────────────────────┐
│                      AGENT SERVICE                        │           │
│                                                           │           │
│  Agent Orchestrator (agent_manager.py)                    │           │
│  ├─ Manages multiple session agents                      │           │
│  ├─ Handles mode changes (Manual/Semi-Auto/Auto)         │           │
│  └─ Tracks metrics across sessions                       │           │
│                                                           │           │
│  EngagementConductorAgent (engagement_conductor.py)       │           │
│  ├─ LangGraph workflow (Perceive→Decide→Act→Learn)       │           │
│  ├─ Publishes events to Redis: ───────────────────────────┘           │
│  │   • agent.status (status changes)                                  │
│  │   • agent.decision (intervention decisions)                        │
│  │   • agent.intervention.executed (execution results)                │
│  └─ Uses Thompson Sampling for decision-making                        │
│                                                                        │
│  API Endpoints:                                                        │
│  ├─ PUT  /api/v1/agent/sessions/{id}/mode                             │
│  ├─ GET  /api/v1/agent/sessions/{id}/status                           │
│  ├─ POST /api/v1/agent/sessions/register                              │
│  ├─ POST /api/v1/agent/sessions/{id}/decisions/{did}/approve          │
│  └─ POST /api/v1/agent/sessions/{id}/decisions/{did}/reject           │
│                                                                        │
│  Middleware (Phase 6):                                                 │
│  ├─ Error Handler (Structured errors, retry-after)                    │
│  └─ Rate Limiter (Token bucket, LLM cost tracking)                    │
│                                                                        │
│  Health Endpoints (Phase 6):                                           │
│  ├─ GET /health (Basic liveness)                                      │
│  ├─ GET /health/ready (Readiness with dependencies)                   │
│  ├─ GET /health/detailed (Full component status)                      │
│  └─ GET /metrics (Agent performance & costs)                          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Integration Points

### 1. Backend → Real-Time Service

**Technology**: Redis Pub/Sub

**Flow**:
1. Agent service publishes events to Redis channel: `session:{sessionId}:events`
2. Real-time service subscribes to these channels via Redis subscriber
3. Events are automatically forwarded to WebSocket clients

**Events Published**:
- `agent.status`: Status changes (MONITORING, WAITING_APPROVAL, INTERVENING, LEARNING, IDLE)
- `agent.decision`: AI makes an intervention decision
- `agent.intervention.executed`: Intervention execution results

**Implementation Files**:
- Backend: [agent-service/app/agents/engagement_conductor.py](agent-service/app/agents/engagement_conductor.py)
  - `_publish_agent_event()` method (line 180)
  - Called from: `_perceive_node()`, `_decide_node()`, `_wait_approval_node()`, `_act_node()`

- Real-Time Service: [real-time-service/src/live/engagement-conductor/engagement-conductor.gateway.ts](real-time-service/src/live/engagement-conductor/engagement-conductor.gateway.ts)
  - Subscribes to Redis channels on client subscription
  - Forwards events to socket rooms

---

### 2. Real-Time Service → Frontend

**Technology**: Socket.IO WebSocket

**Flow**:
1. Frontend subscribes to agent events: `socket.emit('agent:subscribe', { sessionId })`
2. Real-time service creates room: `session:{sessionId}:agent`
3. Events are forwarded to all clients in the room

**Events Received**:
- `agent.status`: Update agent status indicator
- `agent.decision`: Display decision explainer card
- `agent.intervention.executed`: Clear decision, update status

**Implementation Files**:
- Frontend Hook: [frontend/globalconnect/src/features/engagement-conductor/hooks/useAgentState.ts](frontend/globalconnect/src/features/engagement-conductor/hooks/useAgentState.ts)
  - Uses `getSocket()` from `@/lib/socket`
  - Registers event listeners (line 96-98)
  - Updates local state on events

---

### 3. Frontend → Backend API

**Technology**: REST API (Fetch)

**Endpoints Used**:
- `PUT /api/v1/agent/sessions/{sessionId}/mode` - Change agent mode
- `GET /api/v1/agent/sessions/{sessionId}/status` - Get current status
- `POST /api/v1/agent/sessions/{sessionId}/decisions/{id}/approve` - Approve decision
- `POST /api/v1/agent/sessions/{sessionId}/decisions/{id}/reject` - Reject decision

**Implementation Files**:
- Frontend: [useAgentState.ts](frontend/globalconnect/src/features/engagement-conductor/hooks/useAgentState.ts)
  - `setAgentMode()` function (line 121) calls API

- Backend: [agent-service/app/api/v1/agent.py](agent-service/app/api/v1/agent.py)
  - All agent orchestrator endpoints
  - Registered in [main.py](agent-service/app/main.py) (line 100)

---

### 4. UI Components Integration

**Main Dashboard**: [EngagementDashboard.tsx](frontend/globalconnect/src/features/engagement-conductor/components/EngagementDashboard.tsx)

**Integrated Components**:

| Component | Purpose | Location | Status |
|-----------|---------|----------|--------|
| **AgentModeToggle** | Switch between Manual/Semi-Auto/Auto modes | Lines 67-68 | ✅ Connected |
| **AgentStatus** | Real-time agent status with confidence score | Line 69 | ✅ Connected |
| **DecisionExplainer** | Explain AI decisions with reasoning & context | Lines 92-102 | ✅ Connected |
| **OnboardingTour** | Interactive 7-step guide for new users | Lines 35-39 | ✅ Connected |
| **LoadingStates** | Professional skeletons, spinners, error states | Lines 52-58 | ✅ Connected |
| **Demo Simulator** | 60-second engagement recovery simulation | Line 26 | ✅ Connected |
| **Export Utility** | CSV/JSON export with summary stats | Lines 27-31 | ✅ Connected |

**Hooks Used**:
- `useAgentState()` - Agent mode, status, decisions (line 20)
- `useEngagementStream()` - Real-time engagement data (line 14)
- `useInterventions()` - Intervention history (line 17)
- `useOnboardingTour()` - Tour visibility & lifecycle (line 23)

---

## Environment Variables

### Frontend (.env.local)
```bash
# Real-time service (WebSocket)
NEXT_PUBLIC_SOCKET_URL=http://localhost:3002

# Agent service (REST API)
NEXT_PUBLIC_AGENT_SERVICE_URL=http://localhost:8003
```

### Agent Service (.env)
```bash
# Redis for pub/sub
REDIS_URL=redis://localhost:6379

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/engagement_conductor

# LLM (for content generation)
ANTHROPIC_API_KEY=your_key_here

# Optional: LangSmith tracing
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=engagement-conductor
LANGSMITH_API_KEY=your_key_here
```

### Real-Time Service (.env)
```bash
# Redis for pub/sub
REDIS_URL=redis://localhost:6379

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/event_management

# JWT secret
JWT_SECRET=your_secret_here
```

---

## How to Test the Full Integration

### Prerequisites
1. ✅ All services running (see docker-compose.yaml)
2. ✅ Redis running on port 6379
3. ✅ PostgreSQL running (event_management DB + engagement_conductor DB)
4. ✅ Agent service running on port 8003
5. ✅ Real-time service running on port 3002
6. ✅ Frontend running on port 3000

### Step-by-Step Testing

#### 1. Start All Services

```bash
# Terminal 1: Start databases and Redis
docker-compose up postgres redis

# Terminal 2: Start agent service
cd agent-service
python -m uvicorn app.main:app --reload --port 8003

# Terminal 3: Start real-time service
cd real-time-service
npm run dev

# Terminal 4: Start frontend
cd frontend/globalconnect
npm run dev
```

#### 2. Open the Dashboard

1. Navigate to: `http://localhost:3000/dashboard/events/{eventId}/engagement-conductor`
2. The onboarding tour should appear automatically (first visit)
3. Click through the 7-step tour or skip it

#### 3. Test Agent Mode Changes

1. **Manual Mode** (default):
   - Agent status should show "IDLE" or "MONITORING"
   - Click "Manual" button to ensure it's selected
   - Watch the network tab for API call to `/api/v1/agent/sessions/{sessionId}/mode`

2. **Semi-Auto Mode**:
   - Click "Semi-Auto" button
   - Status should update to show the new mode
   - API call should succeed with 200 OK

3. **Auto Mode**:
   - Click "Auto" button
   - Status updates immediately
   - Backend receives mode change

#### 4. Test WebSocket Connection

Open browser console and check for:
```
[Socket] Socket connected { socketId: "abc123" }
[EngagementDashboard] Subscribed to agent events for session: sess_xyz
```

#### 5. Test Real-Time Agent Events

**Simulate agent status change** (backend):
```bash
# Connect to Redis
redis-cli

# Publish a status event
PUBLISH "session:test_session_id:events" '{"type":"agent.status","session_id":"test_session_id","timestamp":"2026-01-04T12:00:00","data":{"status":"MONITORING"}}'

# Publish a decision event
PUBLISH "session:test_session_id:events" '{"type":"agent.decision","session_id":"test_session_id","timestamp":"2026-01-04T12:00:00","data":{"decision":{"interventionType":"POLL","confidence":0.85,"reasoning":"Engagement dropped 15% in 2 minutes. Launching interactive poll to re-engage.","context":{"engagement_bucket":"MEDIUM","session_size_bucket":"LARGE","anomaly_type":"DROP"},"historicalPerformance":{"successRate":0.73,"totalAttempts":24,"isExploring":false},"autoApproved":false,"timestamp":"2026-01-04T12:00:00"}}}'
```

**Expected Frontend Behavior**:
1. Status indicator updates in real-time
2. Decision card appears with full explanation
3. Confidence score displayed
4. Historical performance shown

#### 6. Test Demo Mode

1. Click "🎬 Start Demo" button in header
2. Watch 60-second simulation:
   - Engagement score drops from 75 → 45
   - Anomaly detected (⚠️ alert appears)
   - Agent suggests intervention
   - Decision card shows reasoning
   - Intervention executes
   - Engagement recovers to 78
3. Console logs show demo events every 2 seconds

#### 7. Test Export Functionality

1. Click "📥 Export" button
2. Select format (CSV, JSON, or Copy to Clipboard)
3. File downloads with intervention data
4. Verify summary statistics included

#### 8. Test Error Handling (Phase 6)

1. **Rate Limiting**:
   - Make rapid API calls (>60/min)
   - Should receive 429 error with retry-after header

2. **Error Messages**:
   - Break something (e.g., invalid session ID)
   - Error card should appear with user-friendly message

3. **Health Checks**:
   - Visit: `http://localhost:8003/health/detailed`
   - Should show all components (Redis, DB, Agent) as healthy

---

## Key Features Implemented

### Phase 5 Components
- [x] **AgentModeToggle**: Switch between Manual/Semi-Auto/Auto
- [x] **AgentStatus**: Real-time status with activity timestamp
- [x] **DecisionExplainer**: Transparent AI reasoning with context

### Phase 6 Components
- [x] **OnboardingTour**: 7-step interactive guide
- [x] **LoadingStates**: Skeletons, spinners, empty/error states
- [x] **Demo Simulator**: 60-second engagement recovery scenario
- [x] **Export Utility**: CSV/JSON export with summary stats
- [x] **Error Handling Middleware**: Centralized, structured errors
- [x] **Rate Limiting**: Token bucket with LLM cost tracking
- [x] **Health Endpoints**: Liveness, readiness, detailed status

---

## Data Flow Example

### Scenario: AI Suggests a Poll

```mermaid
sequenceDiagram
    participant Frontend
    participant WebSocket
    participant RealTime
    participant Redis
    participant Agent

    Agent->>Redis: PUBLISH session:123:events<br/>{type: agent.decision, ...}
    Redis->>RealTime: Forward to subscriber
    RealTime->>WebSocket: Emit to room session:123:agent
    WebSocket->>Frontend: agent.decision event
    Frontend->>Frontend: Show DecisionExplainer card
    Frontend->>Frontend: Update AgentStatus to WAITING_APPROVAL

    Note over Frontend: User clicks "Approve"

    Frontend->>Agent: POST /api/v1/agent/.../approve
    Agent->>Agent: Execute intervention
    Agent->>Redis: PUBLISH {type: agent.intervention.executed}
    Redis->>RealTime: Forward
    RealTime->>WebSocket: Forward
    WebSocket->>Frontend: agent.intervention.executed
    Frontend->>Frontend: Clear decision card
    Frontend->>Frontend: Update status to MONITORING
```

---

## Files Modified/Created

### Backend (Agent Service)

**Created**:
- `app/api/v1/agent.py` (246 lines) - Agent orchestrator API
- `app/api/v1/health.py` (215 lines) - Health check endpoints
- `app/middleware/error_handler.py` (387 lines) - Error handling
- `app/middleware/rate_limiter.py` (384 lines) - Rate limiting + cost tracking
- `app/middleware/__init__.py` - Middleware exports

**Modified**:
- `app/main.py` - Registered agent router, middleware, exception handlers
- `app/agents/engagement_conductor.py` - Added WebSocket event publishing
- `app/orchestrator/agent_manager.py` - Added async API wrapper methods
- `app/orchestrator/__init__.py` - Exported agent_manager instance

### Real-Time Service

**Created**:
- `src/live/engagement-conductor/engagement-conductor.gateway.ts` (165 lines)
- `src/live/engagement-conductor/engagement-conductor.module.ts`

**Modified**:
- `src/live/live.module.ts` - Imported EngagementConductorModule

### Frontend

**Created**:
- `src/features/engagement-conductor/hooks/useAgentState.ts` (147 lines)
- `src/features/engagement-conductor/components/OnboardingTour.tsx` (222 lines)
- `src/features/engagement-conductor/components/OnboardingTour.module.css` (241 lines)
- `src/features/engagement-conductor/components/LoadingStates.tsx` (107 lines)
- `src/features/engagement-conductor/components/LoadingStates.module.css` (192 lines)
- `src/features/engagement-conductor/demo/simulator.ts` (308 lines)
- `src/features/engagement-conductor/utils/exportReports.ts` (176 lines)

**Modified**:
- `src/features/engagement-conductor/components/EngagementDashboard.tsx` - Integrated all Phase 5 & 6 components
- `src/features/engagement-conductor/components/EngagementDashboard.module.css` - Added styles
- `src/features/engagement-conductor/components/index.ts` - Exported new components

---

## What's Next?

The user mentioned having **a task before deployment**. The integration is complete and ready for that task. Possible next steps:

1. **Load Testing**: Test with multiple concurrent sessions
2. **Performance Tuning**: Optimize agent response times
3. **Cost Monitoring**: Track LLM costs in production
4. **A/B Testing**: Compare agent modes for effectiveness
5. **Analytics Dashboard**: Visualize agent performance metrics
6. **Production Deployment**: Deploy to staging/production

---

## Support

If you encounter any issues:

1. **Check Service Health**: `http://localhost:8003/health/detailed`
2. **View Logs**:
   - Agent Service: Check terminal or `docker logs agent-service`
   - Real-Time Service: Check terminal or `docker logs real-time-service`
3. **Redis Connection**: Verify with `redis-cli ping`
4. **WebSocket Connection**: Check browser console for connection errors

---

**Status**: ✅ **FULLY INTEGRATED AND OPERATIONAL**

All components from Phase 5 and Phase 6 are now connected with real-time data flow from backend to frontend. The system is ready for testing and deployment.
