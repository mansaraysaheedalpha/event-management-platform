# Backend API Requirements for GlobalConnect Frontend

This document outlines all the GraphQL queries, mutations, and WebSocket events that the frontend expects from the backend.

---

# CRITICAL: Attendee Sign-In Flow for Interactive Features

## The Exact Flow for Chat/Q&A/Polls to Work

When an attendee opens Chat, Q&A, or Polls, this is the **exact sequence** that must happen:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ATTENDEE WEBSOCKET CONNECTION FLOW                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  1. FRONTEND CONNECTS                                                        │
│     ─────────────────────────────────────────────────────────────────────   │
│     const socket = io('http://localhost:3002/events', {                      │
│       auth: { token: 'Bearer <JWT_TOKEN>' },   // ◀── VALIDATE THIS!        │
│       query: { sessionId: 'ses_xxx', eventId: 'evt_xxx' },                   │
│       transports: ['websocket']                                              │
│     });                                                                      │
│                                                                              │
│  2. BACKEND VALIDATES JWT (on connection)                                    │
│     ─────────────────────────────────────────────────────────────────────   │
│     - Extract token from socket.handshake.auth.token                         │
│     - Remove "Bearer " prefix                                                │
│     - Decode and verify JWT                                                  │
│     - Extract userId from payload (sub or userId field)                      │
│     - Store userId in socket.data.userId                                     │
│                                                                              │
│  3. BACKEND SENDS connectionAcknowledged  ◀── CRITICAL! DON'T SKIP!         │
│     ─────────────────────────────────────────────────────────────────────   │
│     socket.emit('connectionAcknowledged', { userId: '<extracted_user_id>' }) │
│                                                                              │
│     ⚠️  Frontend WAITS for this event before proceeding!                     │
│     ⚠️  If not sent, frontend stays stuck on "Connecting..."                 │
│                                                                              │
│  4. FRONTEND EMITS session.join (after receiving connectionAcknowledged)     │
│     ─────────────────────────────────────────────────────────────────────   │
│     socket.emit('session.join', { sessionId, eventId }, callback);           │
│                                                                              │
│  5. BACKEND VALIDATES REGISTRATION  ◀── CRITICAL! CHECK THIS!               │
│     ─────────────────────────────────────────────────────────────────────   │
│     const registration = await db.registration.findFirst({                   │
│       where: {                                                               │
│         eventId: eventId,                                                    │
│         userId: socket.data.userId,          // The user from JWT            │
│         status: { in: ['confirmed', 'checked_in'] }  // NOT cancelled        │
│       }                                                                      │
│     });                                                                      │
│                                                                              │
│     IF NOT REGISTERED:                                                       │
│     ───────────────────                                                      │
│     return callback({                                                        │
│       success: false,                                                        │
│       error: { message: 'You are not registered for this event',             │
│                statusCode: 403 }                                             │
│     });                                                                      │
│                                                                              │
│  6. BACKEND RETURNS SESSION STATE (if registered)                            │
│     ─────────────────────────────────────────────────────────────────────   │
│     const session = await db.session.findUnique({                            │
│       where: { id: sessionId },                                              │
│       select: {                                                              │
│         chatEnabled: true, qaEnabled: true, pollsEnabled: true,              │
│         chatOpen: true, qaOpen: true, pollsOpen: true                        │
│       }                                                                      │
│     });                                                                      │
│                                                                              │
│     socket.join(`session:${sessionId}`);  // Join socket room                │
│                                                                              │
│     callback({                                                               │
│       success: true,                                                         │
│       session: {                                                             │
│         chatEnabled: session.chatEnabled,                                    │
│         qaEnabled: session.qaEnabled,                                        │
│         pollsEnabled: session.pollsEnabled,                                  │
│         chatOpen: session.chatOpen,                                          │
│         qaOpen: session.qaOpen,                                              │
│         pollsOpen: session.pollsOpen                                         │
│       }                                                                      │
│     });                                                                      │
│                                                                              │
│  7. BACKEND SENDS HISTORY EVENTS (immediately after callback)                │
│     ─────────────────────────────────────────────────────────────────────   │
│     socket.emit('chat.history', { messages: [...] });                        │
│     socket.emit('qa.history', { questions: [...] });                         │
│     socket.emit('poll.history', { polls: [...] });                           │
│                                                                              │
│  8. FRONTEND IS NOW FULLY CONNECTED AND OPERATIONAL                          │
│     ─────────────────────────────────────────────────────────────────────   │
│     - Shows chat messages / questions / polls                                │
│     - User can interact (send messages, vote, etc.)                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Backend Checklist for Attendee Sign-In

### Must Implement:

- [ ] **JWT Validation on Connect**
  ```typescript
  // In socket middleware or connection handler
  const authToken = socket.handshake.auth.token;  // "Bearer <jwt>"
  const jwt = authToken.replace('Bearer ', '');
  const decoded = verifyJwt(jwt);
  socket.data.userId = decoded.sub || decoded.userId;
  ```

- [ ] **Send `connectionAcknowledged` Event**
  ```typescript
  // IMMEDIATELY after successful auth
  socket.emit('connectionAcknowledged', { userId: socket.data.userId });
  ```

- [ ] **Handle `session.join` with Registration Check**
  ```typescript
  socket.on('session.join', async ({ sessionId, eventId }, callback) => {
    // 1. Check if user is registered for this event
    const registration = await db.registration.findFirst({
      where: {
        eventId: eventId,
        userId: socket.data.userId,
        status: { in: ['confirmed', 'checked_in'] }
      }
    });

    if (!registration) {
      return callback({
        success: false,
        error: { message: 'You are not registered for this event', statusCode: 403 }
      });
    }

    // 2. Get session state
    const session = await db.session.findUnique({
      where: { id: sessionId },
      select: { chatEnabled: true, qaEnabled: true, pollsEnabled: true,
                chatOpen: true, qaOpen: true, pollsOpen: true }
    });

    // 3. Join room
    socket.join(`session:${sessionId}`);

    // 4. Send success callback with session state
    callback({
      success: true,
      session: { chatEnabled: session.chatEnabled, qaEnabled: session.qaEnabled,
                 pollsEnabled: session.pollsEnabled, chatOpen: session.chatOpen,
                 qaOpen: session.qaOpen, pollsOpen: session.pollsOpen }
    });

    // 5. Send history events
    await sendChatHistory(socket, sessionId);
    await sendQAHistory(socket, sessionId);
    await sendPollHistory(socket, sessionId, socket.data.userId);
  });
  ```

---

# CRITICAL: Data Persistence for Chat, Q&A, and Polls

## Persistence Requirements

All interactive data **MUST persist until the session is deleted**. This means:

1. **Save to database BEFORE broadcasting**
2. **Load from database on session join**
3. **Never store only in memory**

## Database Schema Requirements

### Chat Messages Table
```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id),
  text TEXT NOT NULL,
  parent_message_id UUID REFERENCES chat_messages(id),
  is_edited BOOLEAN DEFAULT FALSE,
  edited_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE chat_reactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id UUID NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  emoji VARCHAR(10) NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(message_id, user_id, emoji)
);

CREATE INDEX idx_chat_session ON chat_messages(session_id, created_at);
```

### Q&A Questions Table
```sql
CREATE TABLE qa_questions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id),
  text TEXT NOT NULL,
  is_anonymous BOOLEAN DEFAULT FALSE,
  status VARCHAR(20) DEFAULT 'pending',  -- pending, approved, dismissed
  is_answered BOOLEAN DEFAULT FALSE,
  tags TEXT[] DEFAULT '{}',
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE qa_answers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id UUID NOT NULL REFERENCES qa_questions(id) ON DELETE CASCADE,
  author_id UUID NOT NULL REFERENCES users(id),
  text TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE qa_upvotes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  question_id UUID NOT NULL REFERENCES qa_questions(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(question_id, user_id)  -- One upvote per user per question
);

CREATE INDEX idx_qa_session ON qa_questions(session_id, created_at);
```

### Polls Tables
```sql
CREATE TABLE polls (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  creator_id UUID NOT NULL REFERENCES users(id),
  question VARCHAR(500) NOT NULL,
  is_active BOOLEAN DEFAULT TRUE,
  expires_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  closed_at TIMESTAMP
);

CREATE TABLE poll_options (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  poll_id UUID NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
  text VARCHAR(200) NOT NULL
);

CREATE TABLE poll_votes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  poll_id UUID NOT NULL REFERENCES polls(id) ON DELETE CASCADE,
  option_id UUID NOT NULL REFERENCES poll_options(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(poll_id, user_id)  -- One vote per user per poll
);

CREATE INDEX idx_polls_session ON polls(session_id, created_at);
CREATE INDEX idx_poll_votes ON poll_votes(poll_id);
```

## History Event Formats

### chat.history Event
```typescript
// Backend sends after session.join
async function sendChatHistory(socket, sessionId) {
  const messages = await db.chatMessage.findMany({
    where: { sessionId },
    include: {
      author: { select: { id: true, firstName: true, lastName: true } },
      parentMessage: {
        include: { author: { select: { id: true, firstName: true, lastName: true } } }
      },
      reactions: true
    },
    orderBy: { createdAt: 'asc' }
  });

  socket.emit('chat.history', {
    messages: messages.map(msg => ({
      id: msg.id,
      text: msg.text,
      timestamp: msg.createdAt.toISOString(),
      isEdited: msg.isEdited,
      editedAt: msg.editedAt?.toISOString() || null,
      authorId: msg.authorId,
      sessionId: msg.sessionId,
      author: { id: msg.author.id, firstName: msg.author.firstName, lastName: msg.author.lastName },
      parentMessage: msg.parentMessage ? {
        id: msg.parentMessage.id,
        text: msg.parentMessage.text,
        author: msg.parentMessage.author
      } : undefined,
      reactionsSummary: computeReactionsSummary(msg.reactions)
    }))
  });
}
```

### qa.history Event
```typescript
async function sendQAHistory(socket, sessionId, userId) {
  const questions = await db.qaQuestion.findMany({
    where: { sessionId },
    include: {
      author: { select: { id: true, firstName: true, lastName: true } },
      answer: { include: { author: { select: { id: true, firstName: true, lastName: true } } } },
      upvotes: true,
      _count: { select: { upvotes: true } }
    },
    orderBy: { createdAt: 'desc' }
  });

  socket.emit('qa.history', {
    questions: questions.map(q => ({
      id: q.id,
      text: q.text,
      isAnonymous: q.isAnonymous,
      status: q.status,
      createdAt: q.createdAt.toISOString(),
      updatedAt: q.updatedAt.toISOString(),
      isAnswered: q.isAnswered,
      tags: q.tags,
      authorId: q.authorId,
      sessionId: q.sessionId,
      author: q.isAnonymous ? { id: '', firstName: 'Anonymous', lastName: '' } : q.author,
      _count: { upvotes: q._count.upvotes },
      answer: q.answer ? {
        id: q.answer.id, text: q.answer.text,
        createdAt: q.answer.createdAt.toISOString(),
        author: q.answer.author
      } : undefined,
      hasUpvoted: q.upvotes.some(u => u.userId === userId)
    }))
  });
}
```

### poll.history Event
```typescript
async function sendPollHistory(socket, sessionId, userId) {
  const polls = await db.poll.findMany({
    where: { sessionId },
    include: {
      creator: { select: { id: true, firstName: true, lastName: true } },
      options: { include: { _count: { select: { votes: true } } } },
      votes: { where: { userId }, select: { optionId: true } },
      _count: { select: { votes: true } }
    },
    orderBy: { createdAt: 'desc' }
  });

  socket.emit('poll.history', {
    polls: polls.map(poll => ({
      poll: {
        id: poll.id,
        question: poll.question,
        isActive: poll.isActive,
        createdAt: poll.createdAt.toISOString(),
        expiresAt: poll.expiresAt?.toISOString() || null,
        creatorId: poll.creatorId,
        sessionId: poll.sessionId,
        creator: poll.creator,
        options: poll.options.map(opt => ({
          id: opt.id, text: opt.text, pollId: poll.id,
          voteCount: opt._count.votes
        })),
        totalVotes: poll._count.votes
      },
      userVotedForOptionId: poll.votes[0]?.optionId || null
    }))
  });
}
```

## Message/Question/Vote Creation Pattern

**ALWAYS follow this order:**

```typescript
// 1. SAVE TO DATABASE FIRST
const message = await db.chatMessage.create({
  data: { sessionId, authorId: userId, text },
  include: { author: { select: { id: true, firstName: true, lastName: true } } }
});

// 2. THEN BROADCAST TO ALL CLIENTS
io.to(`session:${sessionId}`).emit('chat.message.new', {
  id: message.id,
  text: message.text,
  timestamp: message.createdAt.toISOString(),
  isEdited: false,
  editedAt: null,
  authorId: message.authorId,
  sessionId: message.sessionId,
  author: message.author
});

// 3. ACKNOWLEDGE THE SENDER
callback({ success: true, messageId: message.id });
```

## Idempotency for Duplicate Prevention

```typescript
// Store idempotency keys (use Redis or database)
const IDEMPOTENCY_TTL = 24 * 60 * 60; // 24 hours

async function checkAndStoreIdempotency(type: string, key: string, resultId: string): Promise<string | null> {
  const existing = await redis.get(`idempotency:${type}:${key}`);
  if (existing) return existing;  // Return existing result

  await redis.setex(`idempotency:${type}:${key}`, IDEMPOTENCY_TTL, resultId);
  return null;  // No duplicate
}

// Usage in message handler:
socket.on('chat.message.send', async ({ text, idempotencyKey }, callback) => {
  // Check for duplicate request
  const existingId = await checkAndStoreIdempotency('chat', idempotencyKey, 'pending');
  if (existingId && existingId !== 'pending') {
    return callback({ success: true, messageId: existingId });
  }

  // Create message...
  const message = await db.chatMessage.create({...});

  // Update idempotency with actual ID
  await redis.setex(`idempotency:chat:${idempotencyKey}`, IDEMPOTENCY_TTL, message.id);

  // Broadcast and callback...
});
```

## Persistence Summary Table

| Feature | Database Table | History Event | Cascade Delete |
|---------|----------------|---------------|----------------|
| Chat Messages | `chat_messages` | `chat.history` | When session deleted |
| Chat Reactions | `chat_reactions` | Included in messages | When message deleted |
| Q&A Questions | `qa_questions` | `qa.history` | When session deleted |
| Q&A Answers | `qa_answers` | Included in questions | When question deleted |
| Q&A Upvotes | `qa_upvotes` | Included in questions | When question deleted |
| Polls | `polls` | `poll.history` | When session deleted |
| Poll Options | `poll_options` | Included in polls | When poll deleted |
| Poll Votes | `poll_votes` | Count in options | When poll deleted |

---

## Common Problems & Solutions

### Problem: "You are not registered for this event"
**Causes:**
1. Registration check query is wrong
2. User ID not extracted correctly from JWT
3. Registration status is not 'confirmed' or 'checked_in'

**Debug Query:**
```sql
SELECT * FROM registrations
WHERE event_id = '<eventId>'
AND user_id = '<userId>'
AND status IN ('confirmed', 'checked_in');
```

### Problem: Frontend stuck on "Connecting..."
**Cause:** `connectionAcknowledged` event not being sent

**Fix:** Add this immediately after JWT validation:
```typescript
socket.emit('connectionAcknowledged', { userId: socket.data.userId });
```

### Problem: Messages/Questions/Polls disappear on refresh
**Cause:** Data not being saved to database

**Fix:** Always save to database BEFORE broadcasting:
```typescript
// WRONG: Broadcast first
io.emit('chat.message.new', message);
await db.chatMessage.create({...});  // ❌ Wrong order

// CORRECT: Save first
const saved = await db.chatMessage.create({...});  // ✅ Save first
io.emit('chat.message.new', saved);
```

### Problem: History not loading on join
**Cause:** History events not sent after `session.join` callback

**Fix:** Send history events AFTER the callback:
```typescript
socket.on('session.join', async (data, callback) => {
  // ... validation ...

  callback({ success: true, session: {...} });  // First: callback

  // Then: send history
  await sendChatHistory(socket, sessionId);     // Second: history
  await sendQAHistory(socket, sessionId);
  await sendPollHistory(socket, sessionId);
});
```

---

## Table of Contents

1. [Public Events Page](#1-public-events-page)
2. [Attendee My Events Page](#2-attendee-my-events-page)
3. [Attendee Event Details Page](#3-attendee-event-details-page)
4. [Organizer Events Dashboard](#4-organizer-events-dashboard)
5. [Sessions/Agenda](#5-sessionsagenda)
6. [Chat System](#6-chat-system)
7. [Q&A System](#7-qa-system)
8. [Polls System](#8-polls-system)
9. [Authentication & User Types](#9-authentication--user-types) ⚠️ **CRITICAL FIX NEEDED**
10. [Live Dashboard (Organizer)](#10-live-dashboard-organizer)

---

## 1. Public Events Page

### Purpose
Display publicly available events for unauthenticated users to browse and register.

### GraphQL Query

```graphql
query GetPublicEvents($limit: Int, $offset: Int, $includePast: Boolean) {
  publicEvents(limit: $limit, offset: $offset, includePast: $includePast) {
    totalCount
    events {
      id
      name
      description
      startDate
      endDate
      imageUrl
      venue {
        id
        name
      }
    }
  }
}
```

### Expected Response Type

```typescript
interface PublicEventsResponse {
  totalCount: number;
  events: {
    id: string;
    name: string;
    description: string;
    startDate: string; // ISO date string
    endDate: string;   // ISO date string
    imageUrl: string | null;
    venue: {
      id: string;
      name: string;
    } | null;
  }[];
}
```

### Public Event Details Query

```graphql
query GetPublicEventDetails($eventId: ID!) {
  event(id: $eventId) {
    id
    name
    description
    startDate
    endDate
    imageUrl
    venue {
      id
      name
    }
  }
  publicSessionsByEvent(eventId: $eventId) {
    id
    title
    startTime
    endTime
    speakers {
      id
      name
    }
  }
}
```

### Registration Mutation

```graphql
mutation CreateRegistration($registrationIn: RegistrationCreateInput!, $eventId: String!) {
  createRegistration(registrationIn: $registrationIn, eventId: $eventId) {
    id
    status
    ticketCode
  }
}
```

---

## 2. Attendee My Events Page

### Purpose
Display all events the currently logged-in attendee has registered for.

### GraphQL Query

```graphql
query GetMyRegistrations {
  myRegistrations {
    id
    status
    ticketCode
    checkedInAt
    event {
      id
      name
      description
      startDate
      endDate
      status
      imageUrl
      venue {
        id
        name
        address
      }
    }
  }
}
```

### Expected Response Type

```typescript
interface MyRegistration {
  id: string;
  status: "pending" | "confirmed" | "cancelled" | "checked_in";
  ticketCode: string;
  checkedInAt: string | null;
  event: {
    id: string;
    name: string;
    description: string;
    startDate: string;
    endDate: string;
    status: "draft" | "published" | "cancelled" | "completed";
    imageUrl: string | null;
    venue: {
      id: string;
      name: string;
      address: string;
    } | null;
  };
}
```

---

## 3. Attendee Event Details Page

### Purpose
Display detailed event information for a registered attendee, including sessions and interactive features.

### GraphQL Query

```graphql
query GetAttendeeEventDetails($eventId: ID!) {
  myRegistrationForEvent(eventId: $eventId) {
    id
    status
    ticketCode
    checkedInAt
  }
  event(id: $eventId) {
    id
    name
    description
    startDate
    endDate
    status
    imageUrl
    venue {
      id
      name
      address
    }
  }
  publicSessionsByEvent(eventId: $eventId) {
    id
    title
    startTime
    endTime
    status
    chatEnabled
    qaEnabled
    pollsEnabled
    chatOpen
    qaOpen
    pollsOpen
    speakers {
      id
      name
    }
  }
}
```

### Expected Session Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | `string` | Unique session ID (format: `ses_xxx`) |
| `title` | `string` | Session title |
| `startTime` | `string` | ISO date string |
| `endTime` | `string` | ISO date string |
| `status` | `string` | Session status |
| `chatEnabled` | `boolean` | Whether chat feature is enabled for this session |
| `qaEnabled` | `boolean` | Whether Q&A feature is enabled for this session |
| `pollsEnabled` | `boolean` | Whether polls feature is enabled for this session |
| `chatOpen` | `boolean` | Runtime state - is chat currently accepting messages |
| `qaOpen` | `boolean` | Runtime state - is Q&A currently accepting questions |
| `pollsOpen` | `boolean` | Runtime state - are polls currently active |
| `speakers` | `array` | List of speakers with `id` and `name` |

### Important Notes

- **Session ID format**: Must return actual session IDs (`ses_xxx`), NOT event IDs (`evt_xxx`)
- **Registration check**: `myRegistrationForEvent` validates if user can access the event
- **Feature flags**: `chatEnabled`, `qaEnabled`, `pollsEnabled` are set at session creation
- **Runtime state**: `chatOpen`, `qaOpen`, `pollsOpen` are toggled by organizers during the event

---

## 4. Organizer Events Dashboard

### Purpose
Display all events owned/managed by the organizer with management capabilities.

### Get Event By ID Query

```graphql
query GetEventById($id: ID!) {
  event(id: $id) {
    id
    organizationId
    ownerId
    name
    description
    status
    startDate
    endDate
    isPublic
    imageUrl
    registrationsCount
    venue {
      id
      name
      address
    }
  }
}
```

### Create Event Mutation

```graphql
mutation CreateEvent($eventIn: EventCreateInput!) {
  createEvent(eventIn: $eventIn) {
    id
    name
    status
    startDate
    registrationsCount
    imageUrl
  }
}
```

### Update Event Mutation

```graphql
mutation UpdateEvent($id: String!, $eventIn: EventUpdateInput!) {
  updateEvent(id: $id, eventIn: $eventIn) {
    id
    name
    description
    startDate
    endDate
    status
    isPublic
  }
}
```

### Publish Event Mutation

```graphql
mutation PublishEvent($id: String!) {
  publishEvent(id: $id) {
    id
    status
    isPublic
  }
}
```

### Archive/Restore Event Mutations

```graphql
mutation ArchiveEvent($id: String!) {
  archiveEvent(id: $id) {
    id
    isArchived
  }
}

mutation RestoreEvent($id: String!) {
  restoreEvent(id: $id) {
    id
    isArchived
  }
}
```

### Get Attendees By Event Query

```graphql
query GetAttendeesByEvent($eventId: ID!) {
  registrationsByEvent(eventId: $eventId) {
    id
    status
    ticketCode
    checkedInAt
    guestEmail
    guestName
    user {
      id
      first_name
      last_name
      email
    }
  }
}
```

---

## 5. Sessions/Agenda

### Purpose
Manage event sessions with scheduling and feature toggles.

### Get Sessions Query

```graphql
query GetSessionsByEvent($eventId: ID!) {
  sessionsByEvent(eventId: $eventId) {
    id
    title
    startTime
    endTime
    chatEnabled
    qaEnabled
    pollsEnabled
    chatOpen
    qaOpen
    pollsOpen
    speakers {
      id
      name
    }
  }
}
```

### Create Session Mutation

```graphql
mutation CreateSession($sessionIn: SessionCreateInput!) {
  createSession(sessionIn: $sessionIn) {
    id
    title
    startTime
    endTime
    chatEnabled
    qaEnabled
    pollsEnabled
    speakers {
      id
      name
    }
  }
}
```

**SessionCreateInput Expected Fields:**
```typescript
interface SessionCreateInput {
  eventId: string;
  title: string;
  startTime: string;
  endTime: string;
  chatEnabled?: boolean;  // Default: true
  qaEnabled?: boolean;    // Default: true
  pollsEnabled?: boolean; // Default: true
  speakerIds?: string[];
}
```

### Update Session Mutation

```graphql
mutation UpdateSession($id: String!, $sessionIn: SessionUpdateInput!) {
  updateSession(id: $id, sessionIn: $sessionIn) {
    id
    title
    startTime
    endTime
    chatEnabled
    qaEnabled
    pollsEnabled
    speakers {
      id
      name
    }
  }
}
```

### Archive Session Mutation

```graphql
mutation ArchiveSession($id: String!) {
  archiveSession(id: $id) {
    id
  }
}
```

### Toggle Feature Mutations (Runtime Control)

```graphql
# Toggle Chat open/close
mutation ToggleSessionChat($id: String!, $open: Boolean!) {
  toggleSessionChat(id: $id, open: $open) {
    id
    chatOpen
  }
}

# Toggle Q&A open/close
mutation ToggleSessionQA($id: String!, $open: Boolean!) {
  toggleSessionQA(id: $id, open: $open) {
    id
    qaOpen
  }
}

# Toggle Polls open/close
mutation ToggleSessionPolls($id: String!, $open: Boolean!) {
  toggleSessionPolls(id: $id, open: $open) {
    id
    pollsOpen
    pollsEnabled
  }
}
```

### Feature Toggle Logic

| Field | Set At | Purpose |
|-------|--------|---------|
| `chatEnabled` | Session creation/edit | Feature toggle - can attendees ever use chat |
| `qaEnabled` | Session creation/edit | Feature toggle - can attendees ever use Q&A |
| `pollsEnabled` | Session creation/edit | Feature toggle - can polls be created |
| `chatOpen` | Runtime (toggle mutation) | Is chat accepting messages NOW |
| `qaOpen` | Runtime (toggle mutation) | Is Q&A accepting questions NOW |
| `pollsOpen` | Runtime (toggle mutation) | Are polls accepting votes NOW |

**Default State**: `chatOpen`, `qaOpen`, `pollsOpen` should default to `false` - organizer explicitly opens them.

---

## 6. Chat System

### WebSocket Connection

```typescript
const socket = io(REALTIME_URL, {
  auth: { token: `Bearer ${token}` },
  query: { sessionId, eventId },
  transports: ["websocket"]
});
```

### Events the Frontend Emits

#### 1. Join Session Room
```typescript
socket.emit("session.join", { sessionId, eventId }, (response) => {
  // response: { success: boolean, error?: { message, statusCode }, session?: { chatOpen, qaOpen } }
});
```

#### 2. Leave Session Room
```typescript
socket.emit("session.leave", { sessionId });
```

#### 3. Send Chat Message
```typescript
socket.emit("chat.message.send", {
  sessionId: string,
  text: string,           // Max 1000 characters
  idempotencyKey: string, // UUID for deduplication
  replyingToMessageId?: string
}, (response) => {
  // response: { success: boolean, messageId?: string, error?: string }
});
```

**IMPORTANT - Organizer Bypass**:
When `chatOpen = false`, the backend should:
- Block messages from attendees
- Allow messages from organizers/speakers (bypass the check)

#### 4. Edit Chat Message
```typescript
socket.emit("chat.message.edit", {
  messageId: string,
  newText: string,
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```

#### 5. Delete Chat Message
```typescript
socket.emit("chat.message.delete", {
  messageId: string,
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```

#### 6. React to Message
```typescript
socket.emit("chat.message.react", {
  messageId: string,
  emoji: string,
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```

### Events the Frontend Listens To

#### 1. Connection Acknowledged
```typescript
socket.on("connectionAcknowledged", (data: { userId: string }) => {});
```

#### 2. Chat History (sent after session.join)
```typescript
socket.on("chat.history", (data: { messages: ChatMessage[] }) => {});
```

#### 3. New Message
```typescript
socket.on("chat.message.new", (message: ChatMessage) => {});
```

#### 4. Message Updated
```typescript
socket.on("chat.message.updated", (message: ChatMessage) => {});
```

#### 5. Message Deleted
```typescript
socket.on("chat.message.deleted", (data: { messageId: string }) => {});
```

#### 6. Chat Status Changed (organizer toggled)
```typescript
socket.on("chat.status.changed", (data: {
  sessionId: string,
  isOpen: boolean,
  message?: string
}) => {});
```

### ChatMessage Type

```typescript
interface ChatMessage {
  id: string;
  text: string;
  timestamp: string;
  isEdited: boolean;
  editedAt: string | null;
  authorId: string;
  sessionId: string;
  author: {
    id: string;
    firstName: string;
    lastName: string;
  };
  parentMessage?: {
    id: string;
    text: string;
    author: {
      id: string;
      firstName: string;
      lastName: string;
    };
  };
  reactionsSummary?: Record<string, number>; // { "👍": 5, "❤️": 3 }
}
```

---

## 7. Q&A System

### WebSocket Connection
Same as Chat - uses the same socket connection.

### Events the Frontend Emits

#### 1. Ask Question
```typescript
socket.emit("qa.question.ask", {
  text: string,           // Max 500 characters
  isAnonymous: boolean,
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, questionId?: string, error?: string }
});
```

#### 2. Upvote Question (toggle)
```typescript
socket.emit("qna.question.upvote", {
  questionId: string,
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```
**Note**: Users cannot upvote their own questions.

#### 3. Moderate Question (organizer only)
```typescript
socket.emit("qna.question.moderate", {
  questionId: string,
  status: "approved" | "dismissed",
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```

#### 4. Answer Question (organizer/speaker only)
```typescript
socket.emit("qna.question.answer", {
  questionId: string,
  answerText: string,
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```

#### 5. Tag Question (organizer only)
```typescript
socket.emit("qna.question.tag", {
  questionId: string,
  tags: string[],
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```

### Events the Frontend Listens To

#### 1. Q&A History (sent after session.join)
```typescript
socket.on("qa.history", (data: { questions: Question[] }) => {});
```

#### 2. New Question
```typescript
socket.on("qa.question.new", (question: Question) => {});
```

#### 3. Question Updated
```typescript
socket.on("qna.question.updated", (question: Question) => {});
```

#### 4. Question Removed
```typescript
socket.on("qna.question.removed", (data: { questionId: string }) => {});
```

#### 5. Q&A Status Changed
```typescript
socket.on("qa.status.changed", (data: {
  sessionId: string,
  isOpen: boolean,
  message?: string
}) => {});
```

### Question Type

```typescript
interface Question {
  id: string;
  text: string;
  isAnonymous: boolean;
  status: "pending" | "approved" | "dismissed";
  createdAt: string;
  updatedAt: string;
  isAnswered: boolean;
  tags: string[];
  authorId: string;
  sessionId: string;
  author: {
    id: string;
    firstName: string;
    lastName: string;
  };
  _count: {
    upvotes: number;
  };
  answer?: {
    id: string;
    createdAt: string;
    text: string;
    author: {
      id: string;
      firstName: string;
      lastName: string;
    };
  };
}
```

---

## 8. Polls System

### WebSocket Connection
Same as Chat/Q&A - uses the same socket connection.

### Events the Frontend Emits

#### 1. Create Poll (organizer/speaker)
```typescript
socket.emit("poll.create", {
  question: string,        // Max 500 characters
  options: { text: string }[], // 2-10 options, each max 200 chars
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, pollId?: string, error?: string }
});
```

#### 2. Submit Vote (attendee)
```typescript
socket.emit("poll.vote.submit", {
  pollId: string,
  optionId: string,
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, error?: string }
});
```
**Note**: Users can only vote once per poll.

#### 3. Close Poll (organizer)
```typescript
socket.emit("poll.manage", {
  pollId: string,
  action: "close",
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, finalStatus?: string, error?: string }
});
```

#### 4. Start Giveaway (organizer)
```typescript
socket.emit("poll.giveaway.start", {
  pollId: string,
  winningOptionId: string, // Option that wins the prize
  prize: string,           // Max 255 characters
  idempotencyKey: string
}, (response) => {
  // response: { success: boolean, winner?: { id, firstName, lastName }, error?: string }
});
```
**Note**: Poll must be closed before running a giveaway.

### Events the Frontend Listens To

#### 1. Poll History (sent after session.join)
```typescript
socket.on("poll.history", (data: {
  polls: {
    poll: Poll,
    userVotedForOptionId: string | null
  }[]
}) => {});
```

#### 2. Poll Opened (new poll created)
```typescript
socket.on("poll.opened", (poll: Poll) => {});
```

#### 3. Poll Results Updated (someone voted)
```typescript
socket.on("poll.results.updated", (data: {
  poll: Poll,
  userVotedForOptionId: string | null
}) => {});
```

#### 4. Poll Closed
```typescript
socket.on("poll.closed", (data: {
  poll: Poll,
  userVotedForOptionId: string | null
}) => {});
```

#### 5. Giveaway Winner Announced
```typescript
socket.on("poll.giveaway.winner", (data: {
  pollId: string,
  winner: { id: string, firstName: string | null, lastName: string | null } | null,
  prize: string
}) => {});
```

#### 6. Polls Status Changed
```typescript
socket.on("polls.status.changed", (data: {
  sessionId: string,
  isOpen: boolean,
  message: string
}) => {});
```

### Poll Type

```typescript
interface Poll {
  id: string;
  question: string;
  isActive: boolean;
  createdAt: string;
  expiresAt: string | null;
  creatorId: string;
  sessionId: string;
  options: {
    id: string;
    text: string;
    pollId: string;
    voteCount?: number;
  }[];
  totalVotes?: number;
  creator?: {
    id: string;
    firstName: string | null;
    lastName: string | null;
  };
}
```

---

## Access Control Summary

### Registration Validation

When a user tries to join a session room (`session.join`), the backend must:

1. Verify the user has a valid registration for the event
2. Return `{ success: false, error: { message: "...", statusCode: 403 } }` if not registered
3. Return `{ success: true, session: { chatOpen, qaOpen, pollsOpen } }` if valid

### Role-Based Access

| Action | Attendee | Organizer | Speaker |
|--------|----------|-----------|---------|
| Send chat message (when open) | ✅ | ✅ | ✅ |
| Send chat message (when closed) | ❌ | ✅ | ✅ |
| Ask Q&A question | ✅ | ✅ | ✅ |
| Upvote Q&A question | ✅ (not own) | ✅ | ✅ |
| Moderate Q&A question | ❌ | ✅ | ❌ |
| Answer Q&A question | ❌ | ✅ | ✅ |
| Tag Q&A question | ❌ | ✅ | ❌ |
| Vote in poll | ✅ | ✅ | ✅ |
| Create poll | ❌ | ✅ | ✅ |
| Close poll | ❌ | ✅ | ❌ |
| Run giveaway | ❌ | ✅ | ❌ |
| Toggle chat/qa/polls | ❌ | ✅ | ❌ |

---

## Error Response Format

All WebSocket callbacks should follow this format:

```typescript
interface SocketResponse {
  success: boolean;
  error?: {
    message: string;
    statusCode: number;
  } | string;
  // ... other fields specific to the operation
}
```

Common status codes:
- `400` - Bad Request (invalid input)
- `403` - Forbidden (not authorized / not registered)
- `404` - Not Found (resource doesn't exist)
- `409` - Conflict (duplicate vote, etc.)

---

## Important Implementation Notes

1. **Session IDs**: Must use actual session IDs (`ses_xxx`), not event IDs (`evt_xxx`)

2. **Default States**:
   - `chatOpen`, `qaOpen`, `pollsOpen` should default to `false`
   - Organizers explicitly open them during the event

3. **Organizer Chat Bypass**: When `chatOpen = false`:
   - Block attendees from sending messages
   - Allow organizers and speakers to send messages (bypass check)

4. **Idempotency**: All write operations include `idempotencyKey` for deduplication

5. **Real-time Broadcast**: Status changes (`chat.status.changed`, `qa.status.changed`, `polls.status.changed`) must be broadcast to all users in the session room

6. **History Events**: After a successful `session.join`, the backend should automatically emit:
   - `chat.history` with all messages
   - `qa.history` with all questions
   - `poll.history` with all polls and user's votes

---

---

## 9. Authentication & User Types

### Login Mutation

```graphql
mutation Login($input: LoginInput!) {
  login(input: $input) {
    token
    onboardingToken
    user {
      id
      email
      first_name
      last_name
    }
    requires2FA
    userIdFor2FA
  }
}
```

### Critical: User Type Handling

The backend MUST distinguish between **three user scenarios** on login:

| Scenario | Description | Return Value | JWT Contents |
|----------|-------------|--------------|--------------|
| **Organizer with org** | User belongs to an organization | `token` | `{ orgId: "org_xxx", ... }` |
| **Organizer without org** | User registered as organizer but hasn't created org yet | `onboardingToken` | N/A |
| **Attendee** | User registered via `registerAttendee` mutation | `token` | `{ orgId: null, ... }` or no `orgId` field |

### Backend Logic (Pseudocode)

```python
def login(email, password):
    user = authenticate(email, password)

    if user.requires_2fa:
        return { requires2FA: True, userIdFor2FA: user.id }

    # Check user type
    if user.is_attendee:
        # Attendees NEVER need an organization
        # Return regular token WITHOUT orgId
        token = generate_jwt({ userId: user.id })  # No orgId!
        return { token, user }

    # User is an organizer type
    organization = get_user_organization(user.id)

    if organization:
        # Organizer with organization - return token WITH orgId
        token = generate_jwt({ userId: user.id, orgId: organization.id })
        return { token, user }
    else:
        # Organizer without organization - needs onboarding
        onboarding_token = generate_temp_token(user.id)
        return { onboardingToken: onboarding_token }
```

### How to Identify Attendees

Option 1: **User role/type field**
```sql
-- User table has a 'userType' column
SELECT * FROM users WHERE email = ? AND userType = 'attendee'
```

Option 2: **Registration source tracking**
```sql
-- Track how user was registered
SELECT * FROM users WHERE email = ? AND registeredVia = 'attendee_registration'
```

Option 3: **Check if user was created via registerAttendee mutation**
- Users created via `registerAttendee` are attendees
- Users created via `registerUser` are organizers

### Attendee Registration Mutation

```graphql
mutation RegisterAttendee($input: RegisterAttendeeInput!) {
  registerAttendee(input: $input) {
    token
    user {
      id
      email
      first_name
      last_name
    }
  }
}
```

**Important**: This mutation should:
1. Create user with attendee type/flag
2. Return a regular `token` (NOT `onboardingToken`)
3. JWT should NOT contain `orgId`

### Frontend Routing Based on Token

The frontend handles routing like this:

```typescript
// In LoginForm.tsx
if (onboardingToken) {
  // Redirect to create organization
  router.push("/onboarding/create-organization");
} else if (token) {
  const decoded = jwtDecode(token);
  if (decoded.orgId) {
    // Organizer - has organization
    router.push("/dashboard");
  } else {
    // Attendee - no organization needed
    router.push("/attendee");
  }
}
```

### Summary

**The bug**: Backend returns `onboardingToken` for ALL users without an organization, including attendees.

**The fix**: Backend must check if user is an attendee type. If so, return regular `token` (without `orgId` in JWT), NOT `onboardingToken`.

---

## 10. Live Dashboard (Organizer)

### Purpose
Real-time dashboard for organizers to monitor event engagement metrics including messages, poll votes, Q&A activity, reactions, and live check-ins.

### WebSocket Connection

```typescript
const socket = io(REALTIME_URL, {
  auth: { token: `Bearer ${token}` },
  query: { eventId },  // Note: eventId, not sessionId
  transports: ["websocket"]
});
```

### Events the Frontend Emits

#### 1. Join Dashboard Room
```typescript
// IMPORTANT: Must emit AFTER receiving connectionAcknowledged event
socket.emit("dashboard.join", (response: {
  success: boolean;
  error?: string;
}) => {
  // Handle response
});
```

**Note**: The `dashboard.join` should trigger the backend to start broadcasting periodic updates to this organizer.

### Events the Frontend Listens To

#### 1. Connection Acknowledged
```typescript
socket.on("connectionAcknowledged", (data: { userId: string }) => {
  // Now safe to emit dashboard.join
});
```

#### 2. Dashboard Update (Main Data)
```typescript
socket.on("dashboard.update", (data: DashboardData) => {});
```

#### 3. Capacity Updated (Optional)
```typescript
socket.on("dashboard.capacity.updated", (data: CapacityData) => {});
```

#### 4. Metrics Updated (Optional)
```typescript
socket.on("dashboard.metrics.updated", (data: MetricsData) => {});
```

### Dashboard Data Structure

The backend should emit `dashboard.update` events with this structure:

```typescript
interface DashboardData {
  // Chat metrics
  totalMessages: number;           // Total chat messages across all sessions

  // Poll metrics
  totalVotes: number;              // Total poll votes across all sessions
  // OR pollVotes: number;         // Alternative field name (frontend handles both)

  // Q&A metrics
  totalQuestions: number;          // Total questions asked
  // OR questionsAsked: number;    // Alternative field name

  totalUpvotes: number;            // Total upvotes on questions
  // OR questionUpvotes: number;   // Alternative field name

  // Reaction metrics
  totalReactions: number;          // Total emoji reactions on chat messages
  // OR reactions: number;         // Alternative field name

  // Live check-in feed
  recentCheckIns: CheckInItem[];   // Recent attendee check-ins
  // OR liveCheckInFeed: CheckInItem[];  // Alternative field name
}

interface CheckInItem {
  id?: string;                     // Optional unique ID
  name: string;                    // Attendee name (e.g., "John Doe")
  timestamp?: string;              // ISO date string when checked in
}
```

### Example Dashboard Update Payload

```json
{
  "totalMessages": 156,
  "totalVotes": 89,
  "totalQuestions": 23,
  "totalUpvotes": 45,
  "totalReactions": 312,
  "recentCheckIns": [
    {
      "id": "checkin_123",
      "name": "John Doe",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "id": "checkin_124",
      "name": "Jane Smith",
      "timestamp": "2024-01-15T10:31:00Z"
    }
  ]
}
```

### Backend Implementation Requirements

1. **Periodic Broadcasting**: After an organizer joins via `dashboard.join`, the backend should:
   - Immediately send current stats via `dashboard.update`
   - Continue sending updates periodically (e.g., every 5-10 seconds) OR on each relevant event

2. **Aggregate Metrics**: The backend must aggregate metrics across ALL sessions for the event:
   ```sql
   -- Example: Total messages for an event
   SELECT COUNT(*) as totalMessages
   FROM chat_messages
   WHERE session_id IN (SELECT id FROM sessions WHERE event_id = ?)
   ```

3. **Check-in Feed**: Track when attendees check in to the event:
   ```sql
   -- Recent check-ins
   SELECT u.first_name || ' ' || u.last_name as name, r.checked_in_at as timestamp
   FROM registrations r
   JOIN users u ON r.user_id = u.id
   WHERE r.event_id = ? AND r.checked_in_at IS NOT NULL
   ORDER BY r.checked_in_at DESC
   LIMIT 20
   ```

4. **Real-time Updates**: Optionally, emit incremental updates when:
   - A new message is sent → increment `totalMessages`
   - A vote is cast → increment `totalVotes`
   - A question is asked → increment `totalQuestions`
   - An upvote is added → increment `totalUpvotes`
   - A reaction is added → increment `totalReactions`
   - An attendee checks in → add to `recentCheckIns`

### Access Control

- Only **organizers** of the event should be able to join the dashboard room
- Validate that the user making the request owns/manages the event

### Dashboard Metrics Summary

| Metric | Source | Description |
|--------|--------|-------------|
| `totalMessages` | Chat messages | All messages across all sessions |
| `totalVotes` | Poll votes | All votes cast in all polls |
| `totalQuestions` | Q&A questions | All questions asked |
| `totalUpvotes` | Q&A upvotes | All upvotes on questions |
| `totalReactions` | Chat reactions | All emoji reactions |
| `recentCheckIns` | Registrations | Attendees who checked in |

---

*Document generated for GlobalConnect Frontend-Backend API Contract*
