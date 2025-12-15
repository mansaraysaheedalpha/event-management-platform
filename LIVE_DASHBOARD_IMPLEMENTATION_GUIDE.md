# Live Dashboard Real-Time Feature - Complete Implementation Guide

> **Purpose:** This guide explains the complete architecture, data flow, and implementation details for the Live Dashboard feature that displays real-time check-ins, messages, questions, polls, and reactions.

---

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Data Flow Diagram](#data-flow-diagram)
3. [Backend Components](#backend-components)
4. [Frontend Implementation](#frontend-implementation)
5. [Testing the Feature](#testing-the-feature)
6. [Troubleshooting](#troubleshooting)
7. [Production Deployment](#production-deployment)

---

## Architecture Overview

```
┌─────────────────┐     Kafka      ┌─────────────────────┐
│  Event Sources  │ ───────────────▶│  real-time-service │
│  (Check-ins,    │                 │  (Kafka Consumer)  │
│   Simulator)    │                 └─────────┬──────────┘
└─────────────────┘                           │
                                              │ Process & Store
                                              ▼
                                    ┌─────────────────────┐
                                    │       Redis         │
                                    │  (Analytics Hash +  │
                                    │   Check-in Feed)    │
                                    └─────────┬──────────┘
                                              │
                                              │ Poll every 5s
                                              ▼
┌─────────────────┐   WebSocket    ┌─────────────────────┐
│    Frontend     │◀───────────────│    AppGateway       │
│ (Live Dashboard)│  dashboard.    │  (Socket.IO Server) │
│                 │    update      │                     │
└─────────────────┘                └─────────────────────┘
```

### Key Components

| Component | Technology | Purpose |
|-----------|------------|---------|
| Event Simulator | Python + Kafka | Simulates check-in events for testing |
| Kafka | Apache Kafka | Message queue for analytics events |
| DashboardController | NestJS Microservice | Consumes Kafka events |
| DashboardService | NestJS Service | Processes events, stores in Redis |
| Redis | Redis Hash + List | Stores counters and check-in feed |
| AppGateway | Socket.IO | Broadcasts updates to connected clients |
| use-live-dashboard | React Hook | Manages WebSocket connection |
| LiveDashboard | React Component | Renders the dashboard UI |

---

## Data Flow Diagram

### Step 1: Event Generation
```
Check-in happens → Kafka Topic: platform.analytics.check-in.v1
```

**Payload Structure:**
```json
{
  "type": "CHECK_IN_PROCESSED",
  "eventId": "evt_191cc94a7cf1",
  "organizationId": "org_abc123",
  "checkInData": {
    "id": "user_123",
    "name": "John Doe"
  }
}
```

### Step 2: Kafka Consumer (Backend)
**File:** `real-time-service/src/live/dashboard/dashboard.controller.ts`

```typescript
@EventPattern('platform.analytics.check-in.v1')
async handleCheckInEvent(@Payload() data: any) {
  await this.dashboardService.handleAnalyticsEvent(data);
}
```

### Step 3: Redis Storage
**File:** `real-time-service/src/live/dashboard/dashboard.service.ts`

**Redis Keys Created:**
```
dashboard:analytics:{eventId}     → Hash with counters
dashboard:feed:check-in:{eventId} → List with last 10 check-ins
```

**Hash Fields:**
- `totalMessages` - Count of chat messages
- `totalVotes` - Count of poll votes
- `totalQuestions` - Count of Q&A questions
- `totalUpvotes` - Count of question upvotes
- `totalReactions` - Count of emoji reactions

### Step 4: Broadcast to Clients
**File:** `real-time-service/src/app.gateway.ts`

The gateway broadcasts every **5 seconds** to all connected dashboard clients:

```typescript
// Broadcast cycle (every 5 seconds)
const dashboardData = await this.dashboardService.getDashboardData(eventId);
this.server.to(`dashboard:${eventId}`).emit('dashboard.update', dashboardData);
```

---

## Backend Components

### DashboardService Methods

| Method | Purpose |
|--------|---------|
| `handleAnalyticsEvent(payload)` | Processes incoming events, updates Redis |
| `getDashboardData(eventId)` | Fetches aggregated data for broadcasting |
| `updateCheckInFeed(eventId, data)` | Adds new check-in to feed (max 10 items) |

### Supported Event Types

```typescript
type AnalyticsEventType =
  | 'MESSAGE_SENT'       // Increment totalMessages
  | 'POLL_VOTE_CAST'     // Increment totalVotes
  | 'QUESTION_ASKED'     // Increment totalQuestions
  | 'QUESTION_UPVOTED'   // Increment totalUpvotes
  | 'REACTION_SENT'      // Increment totalReactions
  | 'CHECK_IN_PROCESSED' // Add to liveCheckInFeed
```

### WebSocket Events

| Event | Direction | Purpose |
|-------|-----------|---------|
| `dashboard.join` | Client → Server | Join dashboard room for an event |
| `dashboard.update` | Server → Client | Receive dashboard data updates |
| `connectionAcknowledged` | Server → Client | Confirm connection success |
| `systemError` | Server → Client | Receive error notifications |

---

## Frontend Implementation

### Environment Setup

**Required Environment Variables:**
```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:4000/graphql
NEXT_PUBLIC_REALTIME_URL=http://localhost:3002/events
```

**For Production:**
```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/graphql
NEXT_PUBLIC_REALTIME_URL=https://realtime.yourdomain.com/events
```

### Dependencies Required

```bash
npm install socket.io-client
```

### Hook: use-live-dashboard.ts

**Location:** `src/hooks/use-live-dashboard.ts`

```typescript
import { useState, useEffect } from "react";
import { io, Socket } from "socket.io-client";
import { useAuthStore } from "@/store/auth.store";

export interface LiveDashboardData {
  totalMessages: number;
  totalVotes: number;
  totalQuestions: number;
  totalUpvotes: number;
  totalReactions: number;
  liveCheckInFeed: { id: string; name: string }[];
}

export const useLiveDashboard = (eventId: string) => {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [dashboardData, setDashboardData] = useState<LiveDashboardData | null>(null);
  const { token } = useAuthStore();

  useEffect(() => {
    // Guard: Don't connect without eventId or token
    if (!eventId || !token) {
      console.log("Missing eventId or token", { eventId, hasToken: !!token });
      return;
    }

    // Get WebSocket URL from environment
    const realtimeUrl = process.env.NEXT_PUBLIC_REALTIME_URL || "http://localhost:3002/events";

    // Initialize Socket.IO connection
    const newSocket = io(realtimeUrl, {
      query: { eventId },      // Pass eventId in query params
      auth: { token },         // Pass JWT token for authentication
      transports: ['websocket', 'polling'], // Prefer WebSocket
    });

    setSocket(newSocket);

    // Connection established
    newSocket.on("connect", () => {
      console.log("Socket connected:", newSocket.id);
      setIsConnected(true);

      // Join the dashboard room for this event
      newSocket.emit("dashboard.join", (response: { success: boolean; error?: string }) => {
        if (!response.success) {
          console.error("Failed to join dashboard:", response.error);
        } else {
          console.log("Joined dashboard room for event:", eventId);
        }
      });
    });

    // Handle disconnection
    newSocket.on("disconnect", () => {
      console.log("Socket disconnected");
      setIsConnected(false);
    });

    // CRITICAL: Listen for dashboard updates
    newSocket.on("dashboard.update", (data: LiveDashboardData) => {
      console.log("Dashboard update received:", data);
      setDashboardData(data);
    });

    // Handle errors
    newSocket.on("systemError", (error: any) => {
      console.error("System error:", error);
    });

    newSocket.on("connect_error", (error: any) => {
      console.error("Connection error:", error);
    });

    // Cleanup on unmount
    return () => {
      newSocket.off("connect");
      newSocket.off("disconnect");
      newSocket.off("dashboard.update");
      newSocket.off("systemError");
      newSocket.off("connect_error");
      newSocket.disconnect();
    };
  }, [eventId, token]);

  return { isConnected, dashboardData, socket };
};
```

### Component: LiveDashboard.tsx

**Location:** `src/app/(platform)/dashboard/events/[eventId]/_components/live-dashboard.tsx`

```tsx
"use client";

import React from "react";
import { useLiveDashboard } from "@/hooks/use-live-dashboard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AnimatePresence, motion } from "framer-motion";
import { Loader } from "@/components/ui/loader";

interface LiveDashboardProps {
  eventId: string;
}

export const LiveDashboard = ({ eventId }: LiveDashboardProps) => {
  const { isConnected, dashboardData } = useLiveDashboard(eventId);

  // Loading state
  if (!isConnected || !dashboardData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Live Dashboard</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col items-center justify-center py-12">
            {isConnected ? (
              <p>Waiting for first data broadcast...</p>
            ) : (
              <div className="flex items-center">
                <Loader className="h-5 w-5 mr-2 animate-spin" />
                Connecting to real-time service...
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    );
  }

  const {
    totalMessages,
    totalVotes,
    totalQuestions,
    totalUpvotes,
    totalReactions,
    liveCheckInFeed,
  } = dashboardData;

  return (
    <div className="space-y-6">
      {/* Stats Grid */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard title="Total Messages" value={totalMessages} />
        <StatCard title="Poll Votes" value={totalVotes} />
        <StatCard title="Questions Asked" value={totalQuestions} />
        <StatCard title="Question Upvotes" value={totalUpvotes} />
        <StatCard title="Emoji Reactions" value={totalReactions} />
      </div>

      {/* Live Check-in Feed */}
      <Card>
        <CardHeader>
          <CardTitle>Live Check-in Feed</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4 max-h-96 overflow-y-auto">
            {liveCheckInFeed.length > 0 ? (
              <AnimatePresence>
                {liveCheckInFeed.map((checkIn, index) => (
                  <motion.div
                    key={checkIn.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0 }}
                    transition={{ delay: index * 0.1 }}
                    className="flex items-center p-2 bg-green-50 rounded"
                  >
                    <span className="text-green-500 mr-2">✓</span>
                    <span>{checkIn.name} has checked in.</span>
                  </motion.div>
                ))}
              </AnimatePresence>
            ) : (
              <p className="text-muted-foreground text-center py-12">
                No check-ins yet.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

// Helper component for stat cards
const StatCard = ({ title, value }: { title: string; value: number }) => (
  <Card>
    <CardHeader className="pb-2">
      <CardTitle className="text-sm font-medium">{title}</CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-2xl font-bold">{value}</div>
    </CardContent>
  </Card>
);
```

### Using the Component in a Page

**Location:** `src/app/(platform)/dashboard/events/[eventId]/page.tsx`

```tsx
import { LiveDashboard } from "./_components/live-dashboard";

export default function EventDashboardPage({
  params
}: {
  params: { eventId: string }
}) {
  return (
    <div className="container py-6">
      <h1 className="text-2xl font-bold mb-6">Event Dashboard</h1>
      <LiveDashboard eventId={params.eventId} />
    </div>
  );
}
```

---

## Testing the Feature

### Prerequisites

1. **Docker containers running:**
   ```bash
   docker-compose up -d
   ```

2. **Required services:**
   - Kafka (port 9092 external, 29092 internal)
   - Redis (port 6379)
   - real-time-service (port 3002)

### Step 1: Get a Valid Event ID

1. Create an event through the frontend or API
2. Copy the event ID (e.g., `evt_191cc94a7cf1`)

### Step 2: Update the Simulator

**File:** `event_simulator.py`

```python
# Replace with your actual event ID
EVENT_ID = "evt_your_actual_event_id"
```

### Step 3: Install Python Dependencies

```bash
pip install kafka-python
```

### Step 4: Run the Simulator

```bash
# From project root
python event_simulator.py
```

**Expected Output:**
```
--- Event Check-in Simulator ---
Connecting to Kafka at localhost:9092...
✅ Successfully connected to Kafka.
Simulating check-ins for Event ID: evt_191cc94a7cf1
Press Ctrl+C to stop.
Sent check-in: Alex Johnson
Sent check-in: Maria Garcia
...
```

### Step 5: View in Frontend

1. Navigate to: `http://localhost:3000/dashboard/events/{eventId}`
2. You should see:
   - "Connecting to real-time service..." initially
   - Then live check-ins appearing every few seconds

---

## Troubleshooting

### Issue: "Socket connected but no data"

**Symptoms:**
- Console shows "Socket connected"
- Dashboard stuck on "Waiting for first data broadcast..."

**Causes & Solutions:**

1. **User lacks permission `dashboard:read:live`**
   - Check JWT token payload
   - Ensure user role includes this permission

2. **No events being generated**
   - Verify simulator is running
   - Check Kafka connection

3. **Broadcast loop not started**
   - Check real-time-service logs for: `Starting dashboard broadcast loop`

### Issue: "Connection error"

**Symptoms:**
- Console shows "Connection error"
- Socket never connects

**Causes & Solutions:**

1. **Wrong WebSocket URL**
   ```env
   # Correct format (include /events namespace)
   NEXT_PUBLIC_REALTIME_URL=http://localhost:3002/events
   ```

2. **CORS issues**
   - Ensure `http://localhost:3000` is in allowed origins
   - Check `real-time-service/src/main.ts`:
     ```typescript
     app.enableCors({
       origin: ['http://localhost:3000'],
       credentials: true,
     });
     ```

3. **Token not being sent**
   - Ensure user is logged in
   - Check `useAuthStore` has token

### Issue: "Kafka connection failed in simulator"

**Symptoms:**
- Simulator shows "Could not connect to Kafka"

**Causes & Solutions:**

1. **Kafka not accessible at localhost:9092**
   - Verify docker-compose exposes port 9092
   - Check Kafka container is healthy:
     ```bash
     docker-compose ps kafka
     ```

2. **Using wrong broker address**
   - For local development: `localhost:9092`
   - Inside Docker network: `kafka:29092`

### Issue: "Events not reaching dashboard"

**Debug Steps:**

1. **Check Kafka consumer is running:**
   ```bash
   docker-compose logs real-time-service | grep "Kafka"
   ```

2. **Check for event processing:**
   ```bash
   docker-compose logs real-time-service | grep "CHECK_IN"
   ```

3. **Verify Redis is storing data:**
   ```bash
   docker exec -it redis redis-cli
   > HGETALL dashboard:analytics:evt_your_event_id
   > LRANGE dashboard:feed:check-in:evt_your_event_id 0 -1
   ```

---

## Production Deployment

### Environment Variables

**Frontend (.env.production):**
```env
NEXT_PUBLIC_API_URL=https://api.yourdomain.com/graphql
NEXT_PUBLIC_REALTIME_URL=wss://realtime.yourdomain.com/events
```

**Backend (real-time-service):**
```env
PORT=3002
KAFKA_BOOTSTRAP_SERVERS=kafka:29092
REDIS_URL=redis://redis:6379/0
JWT_SECRET=your-production-secret
INTERNAL_API_KEY=your-production-api-key
```

### CORS Configuration

Update `real-time-service/src/main.ts`:
```typescript
app.enableCors({
  origin: [
    'http://localhost:3000',
    'https://yourdomain.com',
    'https://www.yourdomain.com',
  ],
  credentials: true,
});
```

### WebSocket Gateway CORS

Update `real-time-service/src/app.gateway.ts`:
```typescript
@WebSocketGateway({
  cors: {
    origin: [
      'http://localhost:3000',
      'https://yourdomain.com',
    ],
    credentials: true,
  },
  namespace: '/events',
})
```

### Nginx/Load Balancer Configuration

For WebSocket support:
```nginx
location /events {
    proxy_pass http://real-time-service:3002;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 86400;
}
```

### Health Check

The real-time service should expose a health endpoint:
```
GET http://localhost:3002/health
```

---

## Quick Reference

### WebSocket Connection Checklist

- [ ] Environment variable `NEXT_PUBLIC_REALTIME_URL` is set
- [ ] URL includes `/events` namespace
- [ ] User is authenticated (has JWT token)
- [ ] User has `dashboard:read:live` permission
- [ ] `eventId` is valid and passed to hook
- [ ] Docker containers are running (Kafka, Redis, real-time-service)

### Data Structure Reference

**Dashboard Update Payload:**
```typescript
interface LiveDashboardData {
  totalMessages: number;      // Chat messages sent
  totalVotes: number;         // Poll votes cast
  totalQuestions: number;     // Q&A questions asked
  totalUpvotes: number;       // Question upvotes
  totalReactions: number;     // Emoji reactions
  liveCheckInFeed: {          // Last 10 check-ins
    id: string;
    name: string;
  }[];
}
```

### Key Files

| File | Purpose |
|------|---------|
| `frontend/src/hooks/use-live-dashboard.ts` | WebSocket connection hook |
| `frontend/src/app/(platform)/dashboard/events/[eventId]/_components/live-dashboard.tsx` | Dashboard UI |
| `real-time-service/src/app.gateway.ts` | WebSocket server & broadcast |
| `real-time-service/src/live/dashboard/dashboard.service.ts` | Analytics processing |
| `real-time-service/src/live/dashboard/dashboard.controller.ts` | Kafka consumer |
| `event_simulator.py` | Testing tool |

---

**End of Guide**
