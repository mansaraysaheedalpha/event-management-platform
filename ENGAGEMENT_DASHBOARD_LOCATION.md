# Engagement Conductor Dashboard - Location & Access

## 📍 Location

The **Engagement Conductor Dashboard** is now integrated into the **Organizer's Dashboard** as a dedicated tab.

### URL Pattern
```
/dashboard/events/{eventId}/engagement
```

### Example URLs
```
http://localhost:3000/dashboard/events/evt_abc123/engagement
http://localhost:3000/dashboard/events/evt_xyz789/engagement
```

## 🗂️ Dashboard Tab Structure

The organizer's event dashboard now has the following tabs:

1. **Live Dashboard** - Real-time event metrics
2. **🤖 AI Conductor** ⭐ **NEW** - Engagement Conductor with AI agent
3. **Agenda** - Session schedule management
4. **Attendees** - Attendee list and management
5. **Tickets** - Ticket sales and management
6. **History** - Event history timeline
7. **Leaderboard** - Gamification leaderboard
8. **Monetization** - Ads and upsells management

## 🎯 How to Access

### For Event Organizers

1. **Log in** to the platform as an event organizer
2. Navigate to **Dashboard** → **Events**
3. Click on any **event card** to open the event details
4. Click the **"🤖 AI Conductor"** tab in the top navigation

### Direct Navigation

If you already have an event ID, you can navigate directly:
```
/dashboard/events/[YOUR_EVENT_ID]/engagement
```

## 📁 File Structure

### Frontend Route
```
frontend/globalconnect/src/app/(platform)/dashboard/events/[eventId]/
├── page.tsx                    # Main event dashboard (with tabs)
├── engagement/
│   └── page.tsx               # Engagement Conductor page ⭐ NEW
├── leaderboard/
│   └── page.tsx
├── monetization/
│   └── page.tsx
└── _components/
    ├── live-dashboard.tsx
    ├── session-list.tsx
    └── ...
```

### Main Dashboard Integration
The tab is registered in:
- **File**: `frontend/globalconnect/src/app/(platform)/dashboard/events/[eventId]/page.tsx`
- **Line 138**: `<TabsTrigger value="engagement">🤖 AI Conductor</TabsTrigger>`
- **Line 149-151**:
  ```tsx
  <TabsContent value="engagement" className="mt-6">
    <EngagementConductorPage />
  </TabsContent>
  ```

## 🚀 What You'll See

When you open the **🤖 AI Conductor** tab, you'll see:

### On First Visit
- **Interactive Onboarding Tour** (7 steps)
  - Explains agent modes (Manual, Semi-Auto, Auto)
  - Shows how to interpret agent status
  - Demonstrates decision explanations
  - Guide to intervention history
  - Tips on using demo mode and export

### Main Dashboard Components

1. **Header Actions**
   - 🎬 **Start Demo** - 60-second engagement recovery simulation
   - 📥 **Export** - Download intervention reports (CSV/JSON)

2. **Agent Controls Section**
   - **Agent Mode Toggle** - Switch between Manual/Semi-Auto/Auto
   - **Agent Status** - Real-time status indicator with confidence score

3. **Real-Time Engagement Chart**
   - Live engagement score (0-100)
   - Historical trend line
   - Anomaly markers (when detected)

4. **Anomaly Alert** (when active)
   - ⚠️ Alert card showing detected anomaly
   - Severity level and details
   - Detected time

5. **Intervention Suggestion** (when pending)
   - AI-recommended intervention
   - Confidence score
   - Reasoning explanation
   - Approve/Dismiss actions

6. **Decision Explainer** (when agent makes decision)
   - Intervention type and confidence
   - Transparent reasoning
   - Context (engagement level, session size, anomaly type)
   - Historical performance data
   - Auto-approval indicator

7. **Agent Activity Feed**
   - Real-time log of agent actions
   - Intervention execution results
   - Status changes

8. **Intervention History**
   - Timeline of past interventions
   - Success/failure status
   - Performance metrics

## 🔌 Real-Time Connectivity

The dashboard automatically:
- ✅ Initializes WebSocket connection on mount
- ✅ Subscribes to agent events for the session
- ✅ Receives real-time updates:
  - `agent.status` - Status changes
  - `agent.decision` - AI intervention decisions
  - `agent.intervention.executed` - Execution results

### WebSocket Connection

The dashboard uses the existing socket infrastructure:
- **URL**: `ws://localhost:3002/events` (configurable via `NEXT_PUBLIC_SOCKET_URL`)
- **Namespace**: `/events`
- **Authentication**: Uses JWT token from localStorage

### Backend Services

Connects to:
- **Agent Service**: `http://localhost:8003` (configurable via `NEXT_PUBLIC_AGENT_SERVICE_URL`)
- **Real-Time Service**: `http://localhost:3002` (for WebSocket)

## 🔑 Access Control

The engagement conductor dashboard is **only accessible to**:
- Event organizers
- Users with `event:manage` permission
- Users associated with the specific event

Regular attendees **cannot access** this dashboard as it contains sensitive operational controls.

## 🧪 Testing the Dashboard

### Quick Test Steps

1. **Navigate** to any event: `/dashboard/events/{eventId}`
2. **Click** the "🤖 AI Conductor" tab
3. **Watch** for:
   - Onboarding tour appears (first time only)
   - WebSocket connection log in browser console
   - Agent status shows "IDLE" or "MONITORING"

4. **Try changing agent mode**:
   - Click "Semi-Auto" or "Auto"
   - Check network tab for API call to agent service
   - Verify mode change reflected in UI

5. **Start demo mode**:
   - Click "🎬 Start Demo" button
   - Watch 60-second simulation
   - See engagement drop, anomaly alert, intervention suggestion
   - Observe recovery

6. **Test export**:
   - Click "📥 Export"
   - Select CSV, JSON, or Copy to Clipboard
   - Verify file downloads with intervention data

## 📝 Notes

### Session ID Mapping
Currently, the dashboard uses `event_{eventId}_main` as the session ID. This means:
- One agent instance per event (aggregated across all sessions)
- To monitor specific sessions, you may need to update the sessionId parameter

### Future Enhancements
- Session selector to switch between different event sessions
- Multi-session overview dashboard
- Agent performance analytics
- Cost tracking dashboard
- A/B testing different agent modes

## 🐛 Troubleshooting

### Dashboard Not Loading
- Check if all services are running (postgres, redis, agent-service, real-time-service)
- Verify event ID is valid in the URL
- Check browser console for errors

### WebSocket Not Connecting
- Verify real-time-service is running on port 3002
- Check `NEXT_PUBLIC_SOCKET_URL` environment variable
- Ensure JWT token is valid in localStorage

### No Agent Events
- Check if agent-service is running on port 8003
- Verify Redis is running and accessible
- Check agent-service logs for event publishing
- Verify real-time-service is subscribing to Redis channels

### Mode Change Fails
- Check network tab for API call errors
- Verify agent-service `/api/v1/agent/sessions/{id}/mode` endpoint is accessible
- Check CORS configuration if running on different domains

---

**Status**: ✅ **FULLY INTEGRATED**

The Engagement Conductor Dashboard is now accessible through the organizer's event dashboard and ready for testing!
