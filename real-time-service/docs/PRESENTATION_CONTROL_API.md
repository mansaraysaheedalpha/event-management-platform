# Presentation Control API - Backend Documentation

> **Last Updated:** December 2025
> **Service:** real-time-service
> **WebSocket Namespace:** `/events`

---

## Overview

This document describes the WebSocket API for real-time presentation control and synchronization between organizers (presenters) and attendees.

```
┌──────────────┐      content.control       ┌──────────────┐      slide.update      ┌──────────────┐
│   ORGANIZER  │  ─────────────────────────▶│    BACKEND   │  ────────────────────▶│   ATTENDEES  │
│  (Presenter) │                            │   (Socket)   │     (broadcast)       │   (Viewers)  │
└──────────────┘                            └──────────────┘                       └──────────────┘
```

---

## Connection

### WebSocket URL
```
ws://localhost:3002/events
```

### Connection Options
```typescript
const socket = io(`${REALTIME_URL}/events`, {
  auth: { token: `Bearer ${jwtToken}` },
  query: { sessionId, eventId },
  transports: ['websocket'],
});
```

### Connection Events
| Event | Direction | Description |
|-------|-----------|-------------|
| `connect` | Server → Client | Connection established |
| `connectionAcknowledged` | Server → Client | Auth successful, ready to join rooms |
| `disconnect` | Server → Client | Connection lost |

---

## Data Types

### SlideState
```typescript
interface SlideState {
  currentSlide: number;    // 1-indexed (1, 2, 3, ... NOT 0, 1, 2)
  totalSlides: number;     // Total number of slides
  isActive: boolean;       // true = live, false = ended/not started
  slideUrls: string[];     // Array of slide image URLs
}
```

### ContentAction
```typescript
type ContentAction =
  | 'START'       // Start presenting
  | 'STOP'        // End presentation (alias: 'END')
  | 'NEXT_SLIDE'  // Go to next slide
  | 'PREV_SLIDE'  // Go to previous slide
  | 'GO_TO_SLIDE' // Jump to specific slide
```

---

## Events

### 1. Join Session Room

Join a session to receive presentation updates.

**Emit:**
```typescript
socket.emit('session.join', { sessionId, eventId }, (response) => {
  if (response.success) {
    // Joined successfully
    // response.presentationState contains current state (if any)
  }
});
```

**Response:**
```typescript
// Success
{
  success: true,
  session: {
    chatEnabled: boolean,
    qaEnabled: boolean,
    pollsEnabled: boolean,
    reactionsEnabled: boolean
  },
  presentationState: SlideState | null  // Current state if presentation is active
}

// Error
{
  success: false,
  error: { message: string }
}
```

**Note:** `presentationState` is included in the join response, so attendees immediately know the current slide state without needing a separate request.

---

### 2. Request Current State (Optional)

Request the current presentation state. This is optional since `session.join` already returns the state.

**Emit:**
```typescript
socket.emit('content.request_state', { sessionId }, (response) => {
  if (response.success) {
    const state = response.state; // SlideState or null
  }
});
```

**Response:**
```typescript
{
  success: true,
  state: SlideState | null
}
```

---

### 3. Control Presentation (Organizer Only)

Send control commands to manage the presentation.

**Emit:**
```typescript
socket.emit('content.control', {
  sessionId: string,
  action: ContentAction,
  targetSlide?: number,      // Only for GO_TO_SLIDE
  idempotencyKey: string     // UUID v4 - generate new one for each action
}, (response) => {
  if (response.success) {
    const newState = response.newState;
  }
});
```

**Payload by Action:**

| Action | Required Fields | Optional Fields |
|--------|-----------------|-----------------|
| `START` | `sessionId`, `idempotencyKey` | - |
| `STOP` | `sessionId`, `idempotencyKey` | - |
| `NEXT_SLIDE` | `sessionId`, `idempotencyKey` | - |
| `PREV_SLIDE` | `sessionId`, `idempotencyKey` | - |
| `GO_TO_SLIDE` | `sessionId`, `idempotencyKey`, `targetSlide` | `slideNumber` (alias) |

**Response:**
```typescript
// Success
{
  success: true,
  newState: SlideState
}

// Error
{
  success: false,
  error: string
}
```

---

### 4. Receive Slide Updates (All Clients)

Listen for presentation state changes. **This is broadcast to ALL clients in the session room.**

**Listen:**
```typescript
socket.on('slide.update', (state: SlideState) => {
  // Update UI with new state
  console.log(`Slide ${state.currentSlide}/${state.totalSlides}, Active: ${state.isActive}`);
});
```

**Payload:**
```typescript
{
  currentSlide: number,   // 1-indexed
  totalSlides: number,
  isActive: boolean,
  slideUrls: string[]
}
```

---

## Action Details

### START
Starts the presentation from slide 1.

**Backend Behavior:**
1. If already active → Returns current state (no error, no state change)
2. Fetches presentation data from event-lifecycle-service
3. Creates state: `{ currentSlide: 1, totalSlides: N, isActive: true, slideUrls: [...] }`
4. Stores in Redis
5. **Broadcasts `slide.update` to all clients in room**
6. Returns success to organizer

**Example:**
```typescript
socket.emit('content.control', {
  sessionId: 'sess_abc123',
  action: 'START',
  idempotencyKey: crypto.randomUUID()
}, callback);
```

---

### STOP (or END)
Ends the presentation. Both `STOP` and `END` are accepted.

**Backend Behavior:**
1. Gets current state
2. Sets `isActive: false`
3. Stores updated state in Redis
4. **Broadcasts `slide.update` with `isActive: false` to all clients**
5. Returns success to organizer

**Example:**
```typescript
socket.emit('content.control', {
  sessionId: 'sess_abc123',
  action: 'STOP',  // or 'END'
  idempotencyKey: crypto.randomUUID()
}, callback);
```

**Frontend should show:** "Presentation has ended" or similar when `isActive` becomes `false`.

---

### NEXT_SLIDE
Advances to the next slide.

**Backend Behavior:**
1. Gets current state
2. Increments `currentSlide` (max: `totalSlides`)
3. **Broadcasts `slide.update` to all clients**
4. Returns success to organizer

**Bounds:** `currentSlide` will not exceed `totalSlides`

**Example:**
```typescript
socket.emit('content.control', {
  sessionId: 'sess_abc123',
  action: 'NEXT_SLIDE',
  idempotencyKey: crypto.randomUUID()
}, callback);
```

---

### PREV_SLIDE
Goes back to the previous slide.

**Backend Behavior:**
1. Gets current state
2. Decrements `currentSlide` (min: `1`)
3. **Broadcasts `slide.update` to all clients**
4. Returns success to organizer

**Bounds:** `currentSlide` will not go below `1`

**Example:**
```typescript
socket.emit('content.control', {
  sessionId: 'sess_abc123',
  action: 'PREV_SLIDE',
  idempotencyKey: crypto.randomUUID()
}, callback);
```

---

### GO_TO_SLIDE
Jumps to a specific slide number.

**Backend Behavior:**
1. Gets current state
2. Sets `currentSlide` to `targetSlide` (bounds: 1 to `totalSlides`)
3. **Broadcasts `slide.update` to all clients**
4. Returns success to organizer

**Example:**
```typescript
socket.emit('content.control', {
  sessionId: 'sess_abc123',
  action: 'GO_TO_SLIDE',
  targetSlide: 5,  // or slideNumber: 5
  idempotencyKey: crypto.randomUUID()
}, callback);
```

---

## Frontend Implementation Guide

### Displaying Slides

```typescript
// Get slide URL (convert 1-indexed to 0-indexed array access)
const getCurrentSlideUrl = (state: SlideState): string | null => {
  if (!state || !state.isActive || !state.slideUrls?.length) {
    return null;
  }
  return state.slideUrls[state.currentSlide - 1];
};
```

### UI States

| Condition | Display |
|-----------|---------|
| `state === null` | "Waiting for presentation to start..." |
| `state.isActive === false` | "Presentation has ended" |
| `state.isActive === true` | Show slide from `slideUrls[currentSlide - 1]` |

### Idempotency Key

**Important:** Generate a new UUID for each action to prevent duplicate request errors.

```typescript
const sendAction = (action: ContentAction, targetSlide?: number) => {
  socket.emit('content.control', {
    sessionId,
    action,
    targetSlide,
    idempotencyKey: crypto.randomUUID()  // NEW UUID each time!
  }, handleResponse);
};
```

---

## Error Handling

### Error Responses

| Error | Cause | Solution |
|-------|-------|----------|
| `Duplicate action request` | Same `idempotencyKey` used twice within 60s | Generate new UUID for each action |
| `Presentation is not active` | Trying to navigate when presentation hasn't started | Call START first |
| `No presentation found for session` | No slides uploaded for this session | Upload presentation via REST API |
| `Not authorized to control presentation` | User is not organizer/speaker | Check user permissions |
| `slideNumber or targetSlide is required` | GO_TO_SLIDE without target | Include `targetSlide` parameter |

---

## Complete Frontend Example

```typescript
import { io, Socket } from 'socket.io-client';
import { useEffect, useState, useCallback } from 'react';

interface SlideState {
  currentSlide: number;
  totalSlides: number;
  isActive: boolean;
  slideUrls: string[];
}

export function usePresentationControl(
  sessionId: string,
  eventId: string,
  canControl: boolean
) {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [slideState, setSlideState] = useState<SlideState | null>(null);
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    const newSocket = io(`${process.env.NEXT_PUBLIC_REALTIME_URL}/events`, {
      auth: { token: `Bearer ${getToken()}` },
      query: { sessionId, eventId },
      transports: ['websocket'],
    });

    newSocket.on('connect', () => setIsConnected(true));
    newSocket.on('disconnect', () => setIsConnected(false));

    // Listen for slide updates (ALL clients receive this)
    newSocket.on('slide.update', (state: SlideState) => {
      setSlideState(state);
    });

    // Join session room
    newSocket.emit('session.join', { sessionId, eventId }, (response) => {
      if (response.success && response.presentationState) {
        setSlideState(response.presentationState);
      }
    });

    setSocket(newSocket);

    return () => {
      newSocket.disconnect();
    };
  }, [sessionId, eventId]);

  // Control functions (organizer only)
  const sendControl = useCallback((action: string, targetSlide?: number) => {
    if (!socket || !canControl) return;

    socket.emit('content.control', {
      sessionId,
      action,
      targetSlide,
      idempotencyKey: crypto.randomUUID()
    }, (response) => {
      if (!response.success) {
        console.error('Control failed:', response.error);
      }
    });
  }, [socket, sessionId, canControl]);

  const startPresentation = () => sendControl('START');
  const stopPresentation = () => sendControl('STOP');
  const nextSlide = () => sendControl('NEXT_SLIDE');
  const prevSlide = () => sendControl('PREV_SLIDE');
  const goToSlide = (n: number) => sendControl('GO_TO_SLIDE', n);

  return {
    slideState,
    isConnected,
    startPresentation,
    stopPresentation,
    nextSlide,
    prevSlide,
    goToSlide,
    canControl
  };
}
```

---

## Testing Checklist

- [ ] START initializes with `currentSlide: 1` (not 0)
- [ ] START sets `isActive: true`
- [ ] START broadcasts `slide.update` to all clients in room
- [ ] Clicking START when already active returns current state (no error)
- [ ] STOP sets `isActive: false`
- [ ] STOP broadcasts `slide.update` to all clients
- [ ] Attendee UI shows "ended" message when `isActive: false`
- [ ] NEXT_SLIDE increments and broadcasts
- [ ] NEXT_SLIDE stops at `totalSlides` (doesn't go past last slide)
- [ ] PREV_SLIDE decrements and broadcasts
- [ ] PREV_SLIDE stops at `1` (doesn't go below first slide)
- [ ] GO_TO_SLIDE jumps to correct slide and broadcasts
- [ ] Attendees see slide changes immediately
- [ ] New attendees joining mid-presentation see current slide state

---

## File References

| File | Description |
|------|-------------|
| `src/live/content/content.gateway.ts` | WebSocket event handlers |
| `src/live/content/content.service.ts` | Business logic for presentation control |
| `src/live/content/dto/content-control.dto.ts` | DTO validation for control events |
| `src/live/content/dto/presentation-state.dto.ts` | SlideState type definition |

---

## Contact

For questions about this API, check the service logs:
```bash
docker-compose logs -f real-time-service
```
