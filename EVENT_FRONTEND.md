# GlobalConnect Event System - Feature Documentation

A comprehensive overview of all major features in the GlobalConnect event management platform.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [User Roles & Authentication](#user-roles--authentication)
3. [Public Event Experience](#public-event-experience)
4. [Organizer Dashboard](#organizer-dashboard)
5. [Attendee Portal](#attendee-portal)
6. [Session Management](#session-management)
7. [Interactive Session Features](#interactive-session-features)
8. [Real-Time Communication](#real-time-communication)
9. [Presentation System](#presentation-system)
10. [Live Dashboard](#live-dashboard)

---

## System Architecture

### Tech Stack
- **Frontend**: Next.js 14 with App Router
- **State Management**: Apollo Client (GraphQL), Zustand (Auth)
- **Real-Time**: Socket.io WebSocket connections
- **UI Components**: Shadcn/ui with Radix primitives
- **Styling**: Tailwind CSS

### Route Groups
The application uses Next.js route groups to separate concerns:

| Route Group | Path | Purpose |
|-------------|------|---------|
| `(public)` | `/`, `/events/[eventId]` | Public-facing event pages |
| `(platform)` | `/dashboard/*` | Organizer management dashboard |
| `(attendee)` | `/attendee/*` | Registered attendee portal |

---

## User Roles & Authentication

### Role Types

#### 1. Public Visitors
- View public event listings
- Access event detail pages
- Register as attendees for events

#### 2. Organizers
- Full event management capabilities
- Access to organizer dashboard
- Control over sessions, speakers, venues
- Real-time event monitoring

#### 3. Attendees
- Access to registered events
- Participate in interactive features
- View presentations and sessions

### Authentication Flow

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Login/Register │────▶│   Auth Provider  │────▶│  Role-Based     │
│      Forms      │     │  (Zustand Store) │     │    Routing      │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

- **AuthGuard Component**: Protects routes based on authentication status
- **Token Management**: JWT tokens stored and managed via auth store
- **Separate Registration**: Organizers and attendees have different registration flows

---

## Public Event Experience

### Event Discovery (`/events`)
- Browse all published events
- Filter and search capabilities
- Event cards with key information

### Event Detail Page (`/events/[eventId]`)

#### Components:
- **Event Hero**: Banner image, title, date, location
- **Session Timeline**: Chronological list of all sessions
- **Registration Card**: Sticky CTA for event registration
- **Registration Modal**: Attendee registration form

#### Data Displayed:
- Event title, description, dates
- Venue information with address
- Session schedule with speakers
- Ticket/registration information

---

## Organizer Dashboard

### Navigation Structure
```
Dashboard
├── Events
│   ├── Event List
│   └── Event Detail
│       ├── Sessions
│       ├── Live Dashboard
│       └── Event Settings
├── Speakers
├── Venues
└── Blueprints
```

### Event Management

#### Create Event
- Title, description, dates
- Venue selection
- Cover image upload
- Visibility settings

#### Event Detail View (`/dashboard/events/[eventId]`)
- **Event Detail Header**: Summary with edit capabilities
- **Session List**: All sessions with management options
- **Event History Timeline**: Activity log
- **Live Dashboard**: Real-time event monitoring

### Session Management

#### Add Session Modal
Fields:
- Session title
- Date (within event date range)
- Start/End times
- Speaker assignment (multi-select)
- Interactive feature toggles:
  - Chat enabled
  - Q&A enabled
  - Polls enabled

#### Edit Session Modal
- All fields from add modal
- Current values pre-populated
- Real-time validation

### Speaker Management (`/speakers`)
- Create, edit, delete speakers
- Profile photo upload
- Bio and social links
- Assign to sessions

### Venue Management (`/venues`)
- Create, edit, delete venues
- Address and capacity information
- Location mapping

### Blueprints (`/blueprints`)
- Event templates for quick creation
- Reusable session structures

---

## Attendee Portal

### Attendee Dashboard (`/attendee/events/[eventId]`)

#### Session Card Features
Each session displays:
- Title, time, speakers
- Interactive feature buttons (when enabled):
  - Chat button with message indicator
  - Q&A button with question count
  - Polls button with active poll indicator
  - Presentation viewer

#### Interactive Panels
Slide-out sheets for each feature:
- Full-height side panels
- Real-time updates
- Participation tracking

---

## Session Management

### Session Data Model

```typescript
interface Session {
  id: string;
  title: string;
  startTime: string;
  endTime: string;
  speakers: Speaker[];

  // Interactive Features - Configuration
  chatEnabled: boolean;
  qaEnabled: boolean;
  pollsEnabled: boolean;

  // Interactive Features - Runtime State
  chatOpen: boolean;
  qaOpen: boolean;
  pollsOpen: boolean;

  // Presentation
  presentation?: Presentation;
  presentationStatus?: string;
}
```

### Feature Toggle Pattern

Each interactive feature uses a two-state system:

| State | Purpose | Controlled By |
|-------|---------|---------------|
| `enabled` | Session-level configuration | Session creation/edit |
| `open` | Runtime on/off toggle | Live dashboard controls |

This allows organizers to:
1. Configure which features are available for a session
2. Control when features are active during the event

---

## Interactive Session Features

### 1. Chat System

#### Capabilities
- Real-time message exchange
- Message history persistence
- User identification
- Typing indicators

#### Hook: `useSessionChat`
```typescript
const {
  messages,
  isConnected,
  isJoined,
  chatOpen,
  sendMessage,
  clearError
} = useSessionChat(sessionId, eventId, initialChatOpen);
```

#### UI Component: `SessionChat`
- Message list with auto-scroll
- Input field with send button
- Connection status indicator
- Error handling

### 2. Q&A System

#### Capabilities
- Question submission
- Upvoting questions
- Mark as answered
- Question moderation

#### Hook: `useSessionQA`
```typescript
const {
  questions,
  isConnected,
  isJoined,
  qaOpen,
  submitQuestion,
  upvoteQuestion,
  markAsAnswered
} = useSessionQA(sessionId, eventId, initialQaOpen);
```

#### UI Component: `SessionQA`
- Question list sorted by votes
- Submit new question form
- Upvote buttons
- Answered status toggle (organizers)

### 3. Polls System

#### Capabilities
- Create polls with multiple options
- Real-time voting
- Live results display
- Close polls
- Giveaway winner selection from voters

#### Hook: `useSessionPolls`
```typescript
const {
  polls,
  activePolls,
  closedPolls,
  userVotes,
  pollsOpen,
  latestGiveaway,
  createPoll,
  submitVote,
  closePoll,
  startGiveaway,
  hasVoted,
  getUserVote
} = useSessionPolls(sessionId, eventId, initialPollsOpen);
```

#### UI Component: `SessionPolls`

**Organizer View:**
- Create new poll form
- View all polls (active & closed)
- See real-time results with vote counts
- Close active polls
- Run giveaway (random winner selection)
- Toggle polls open/closed

**Attendee View:**
- View active polls
- Submit votes (one per poll)
- See results after voting
- View closed poll results

#### Poll Data Structure
```typescript
interface Poll {
  id: string;
  question: string;
  options: PollOption[];
  isActive: boolean;
  totalVotes: number;
  createdAt: string;
  closedAt?: string;
}

interface PollOption {
  id: string;
  text: string;
  voteCount: number;
  percentage: number;
}
```

---

## Real-Time Communication

### WebSocket Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client    │────▶│  Socket.io       │────▶│   Backend       │
│   Hooks     │◀────│  Connection      │◀────│   Services      │
└─────────────┘     └──────────────────┘     └─────────────────┘
```

### Connection Flow

1. **Initialize**: Create socket connection with auth token
2. **Join Session**: Send `session:join` event with sessionId
3. **Receive State**: Get initial state (messages, questions, polls)
4. **Real-Time Updates**: Listen for feature-specific events
5. **Cleanup**: Leave session and disconnect on unmount

### Event Types

| Event | Direction | Purpose |
|-------|-----------|---------|
| `session:join` | Client → Server | Join session room |
| `session:joined` | Server → Client | Confirm join with initial state |
| `session:state` | Server → Client | Full state update |
| `chat:message` | Bidirectional | Chat messages |
| `qa:question` | Bidirectional | Q&A questions |
| `qa:upvote` | Bidirectional | Question upvotes |
| `polls:poll` | Server → Client | New poll created |
| `polls:vote` | Client → Server | Submit vote |
| `polls:results` | Server → Client | Updated results |
| `polls:closed` | Server → Client | Poll closed |
| `polls:giveaway` | Server → Client | Giveaway winner |

### Error Handling

- Connection retry with exponential backoff
- Access denied handling
- Optimistic updates with rollback
- User-friendly error messages

---

## Presentation System

### Upload Flow

1. Organizer uploads presentation file
2. File stored and processed
3. Presentation linked to session
4. Available for viewing during session

### Presentation Viewer

#### Components:
- **UploadPresentationModal**: File upload interface
- **PresentationViewer**: Display component
- **PresentationStatus**: Current slide/status indicator

#### Features:
- Slide navigation
- Full-screen mode
- Real-time sync (presenter controls)

---

## Live Dashboard

### Overview (`/dashboard/events/[eventId]`)

The live dashboard provides real-time monitoring:

#### Hook: `useLiveDashboard`
```typescript
const {
  stats,
  isConnected,
  refreshStats
} = useLiveDashboard(eventId);
```

#### Displayed Metrics:
- Total attendees
- Active sessions
- Chat message count
- Q&A question count
- Poll participation rates

#### Session Controls:
Each session card shows:
- Current status (upcoming/live/ended)
- Interactive feature toggles
- Quick actions (edit, view, manage)

---

## GraphQL Operations

### Queries

| Query | Purpose |
|-------|---------|
| `GET_EVENTS_QUERY` | List all events for organizer |
| `GET_EVENT_QUERY` | Single event details |
| `GET_SESSIONS_BY_EVENT_QUERY` | Sessions for an event |
| `GET_PUBLIC_EVENT_QUERY` | Public event view |
| `publicSessionsByEvent` | Public sessions for attendees |

### Mutations

| Mutation | Purpose |
|----------|---------|
| `CREATE_EVENT_MUTATION` | Create new event |
| `UPDATE_EVENT_MUTATION` | Edit event details |
| `CREATE_SESSION_MUTATION` | Add session to event |
| `UPDATE_SESSION_MUTATION` | Edit session |
| `TOGGLE_SESSION_CHAT_MUTATION` | Open/close chat |
| `TOGGLE_SESSION_QA_MUTATION` | Open/close Q&A |
| `TOGGLE_SESSION_POLLS_MUTATION` | Open/close polls |

---

## Security Considerations

### Authentication
- JWT token-based authentication
- Token refresh mechanism
- Secure storage (httpOnly cookies/secure storage)

### Authorization
- Role-based access control
- Event ownership verification
- Session-level permissions

### WebSocket Security
- Token validation on connection
- Session access verification
- Rate limiting on events

---

## File Structure Overview

```
src/
├── app/
│   ├── (public)/           # Public pages
│   │   ├── events/
│   │   └── page.tsx
│   ├── (platform)/         # Organizer dashboard
│   │   └── dashboard/
│   │       ├── events/
│   │       ├── speakers/
│   │       ├── venues/
│   │       └── blueprints/
│   └── (attendee)/         # Attendee portal
│       └── attendee/
│           └── events/
├── components/
│   ├── ui/                 # Shadcn components
│   ├── features/           # Feature components
│   └── layout/             # Layout components
├── graphql/                # GraphQL operations
│   ├── events.graphql.ts
│   ├── attendee.graphql.ts
│   └── public.graphql.ts
├── hooks/                  # Custom hooks
│   ├── use-session-chat.ts
│   ├── use-session-qa.ts
│   ├── use-session-polls.ts
│   └── use-live-dashboard.ts
└── lib/                    # Utilities
    └── apollo-provider.tsx
```

---

## Future Considerations

Potential enhancements:
- Push notifications for session updates
- Offline support for attendees
- Analytics dashboard for organizers
- Recording/replay of sessions
- Multi-language support
- Calendar integration
- Mobile app companion

---

*Document generated for GlobalConnect Event Management Platform*
