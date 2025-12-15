# GlobalConnect Real-Time Service - Frontend Integration Guide

> **Document Version:** 1.0
> **Last Updated:** December 2025
> **Backend Service:** real-time-service (NestJS + Socket.io)
> **Port:** 3002

---

## Table of Contents

1. [Connection Setup](#1-connection-setup)
2. [Authentication](#2-authentication)
3. [Room Structure](#3-room-structure)
4. [Chat Feature](#4-chat-feature)
5. [Polls Feature](#5-polls-feature)
6. [Q&A Feature](#6-qa-feature)
7. [Direct Messaging](#7-direct-messaging)
8. [Emoji Reactions](#8-emoji-reactions)
9. [Gamification](#9-gamification)
10. [Live Dashboard](#10-live-dashboard)
11. [Notifications](#11-notifications)
12. [Content/Presentation Control](#12-contentpresentation-control)
13. [Agenda Updates](#13-agenda-updates)
14. [Permissions Reference](#14-permissions-reference)
15. [Error Handling](#15-error-handling)
16. [TypeScript Interfaces](#16-typescript-interfaces)
17. [Quick Start Example](#17-quick-start-example)

---

## 1. Connection Setup

### WebSocket Configuration

```typescript
import { io, Socket } from 'socket.io-client';

const SOCKET_URL = 'http://localhost:3002/events';

const socket: Socket = io(SOCKET_URL, {
  auth: {
    token: `Bearer ${accessToken}`  // Required - JWT access token
  },
  query: {
    sessionId: '<SESSION_ID>',  // Optional: for session-based features
    eventId: '<EVENT_ID>'       // Optional: for event-based features
  },
  transports: ['websocket'],
  reconnection: true,
  reconnectionAttempts: 5,
  reconnectionDelay: 1000
});
```

### Connection Events

```typescript
// Connection successfully established
socket.on('connectionAcknowledged', (data: { userId: string }) => {
  console.log('Connected as user:', data.userId);
});

// System errors (auth failures, etc.)
socket.on('systemError', (error: { message: string; reason: string }) => {
  console.error('System error:', error.message);
  // Handle reconnection or show error to user
});

// Disconnection
socket.on('disconnect', (reason: string) => {
  console.log('Disconnected:', reason);
});

// Reconnection
socket.on('reconnect', (attemptNumber: number) => {
  console.log('Reconnected after', attemptNumber, 'attempts');
});
```

### Production Configuration

```typescript
const socket = io(process.env.NEXT_PUBLIC_REALTIME_URL + '/events', {
  auth: {
    token: `Bearer ${accessToken}`
  },
  transports: ['websocket', 'polling'], // Fallback to polling
  reconnection: true,
  reconnectionAttempts: 10,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 5000,
  timeout: 20000
});
```

---

## 2. Authentication

### JWT Payload Structure

The backend expects a JWT with this structure (automatically included from your auth system):

```typescript
interface JwtPayload {
  sub: string;              // User ID (required)
  email: string;            // User email (required)
  orgId: string;            // Active organization ID (required)
  role?: string;            // User role (e.g., 'ADMIN', 'MEMBER')
  permissions?: string[];   // Array of permission strings
  tier?: 'default' | 'vip'; // User tier for rate limiting
  preferredLanguage?: string;
  sponsorId?: string;
}
```

### Token Passing

The token is passed via the `auth` option during connection. The backend automatically:

1. Verifies the JWT signature
2. Validates the user exists and is active
3. Extracts permissions for authorization checks
4. Joins the user to their private room (`user:{userId}`)

### Token Refresh

If the token expires during a session, reconnect with the new token:

```typescript
socket.auth = { token: `Bearer ${newAccessToken}` };
socket.connect();
```

---

## 3. Room Structure

The backend uses rooms to broadcast events to specific groups of users.

| Room Pattern | Purpose | How to Join |
|--------------|---------|-------------|
| `user:{userId}` | Private notifications, DMs, achievements | **Auto-joined on connect** |
| `session:{sessionId}` | Chat, polls, Q&A, reactions | `session.join` event |
| `session:{sessionId}:moderation` | Moderator-only Q&A events | Auto-joined if has `qna:moderate` |
| `event:{eventId}` | Event-wide notifications, agenda updates | Future: `event.join` |
| `dashboard:{eventId}` | Admin dashboard metrics | `dashboard.join` event |

### Joining a Session Room

**IMPORTANT:** You must join a session room to receive chat, poll, Q&A, and reaction events.

```typescript
// Join a session room (call this when user enters a session view)
socket.emit('session.join', { sessionId: 'sess_abc123' });

// Leave a session room (call this when user leaves session view)
socket.emit('session.leave', { sessionId: 'sess_abc123' });
```

### Best Practice: Room Management

```typescript
// In your session/event component
useEffect(() => {
  if (sessionId && socket.connected) {
    socket.emit('session.join', { sessionId });
  }

  return () => {
    if (sessionId && socket.connected) {
      socket.emit('session.leave', { sessionId });
    }
  };
}, [sessionId, socket.connected]);
```

---

## 4. Chat Feature

Real-time chat within a session. Supports text messages, replies, reactions, editing, and deletion.

### 4.1 Send Message

**Event:** `chat.message.send`
**Direction:** Client → Server
**Permission:** None (must be session participant)

```typescript
// Payload
interface SendMessagePayload {
  text: string;              // Required, max 1000 characters
  idempotencyKey: string;    // Required, UUID v4 (prevents duplicates)
  replyingToMessageId?: string;  // Optional, UUID v4 (for replies)
}

// Send
socket.emit('chat.message.send', {
  text: 'Hello everyone!',
  idempotencyKey: uuidv4(),
  replyingToMessageId: undefined  // or message ID if replying
});

// Response (callback style)
socket.emit('chat.message.send', payload, (response) => {
  if (response.success) {
    console.log('Message sent:', response.messageId);
  } else {
    console.error('Failed:', response.error);
  }
});
```

### 4.2 Receive New Message

**Event:** `chat.message.new`
**Direction:** Server → Client
**Room:** `session:{sessionId}`

```typescript
interface ChatMessage {
  id: string;
  text: string;
  timestamp: string;        // ISO 8601 format
  isEdited: boolean;
  editedAt: string | null;
  authorId: string;
  sessionId: string;
  author: {
    id: string;
    firstName: string;
    lastName: string;
  };
  parentMessage?: {         // Present if this is a reply
    id: string;
    text: string;
    author: {
      id: string;
      firstName: string;
      lastName: string;
    };
  };
  reactionsSummary?: Record<string, number>;  // e.g., { "👍": 3, "❤️": 1 }
}

socket.on('chat.message.new', (message: ChatMessage) => {
  // Add message to chat UI
  setChatMessages(prev => [...prev, message]);
});
```

### 4.3 Edit Message

**Event:** `chat.message.edit`
**Direction:** Client → Server
**Constraint:** Within 5 minutes of sending, own messages only

```typescript
interface EditMessagePayload {
  messageId: string;       // Required, UUID v4
  newText: string;         // Required, max 1000 characters
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('chat.message.edit', {
  messageId: 'msg_abc123',
  newText: 'Updated message text',
  idempotencyKey: uuidv4()
});
```

**Broadcast Event:** `chat.message.updated`

```typescript
socket.on('chat.message.updated', (message: ChatMessage) => {
  // Update message in UI
  setChatMessages(prev =>
    prev.map(m => m.id === message.id ? message : m)
  );
});
```

### 4.4 Delete Message

**Event:** `chat.message.delete`
**Direction:** Client → Server
**Permission:** `chat:delete:own` (own messages) or `chat:delete:any` (moderator)

```typescript
interface DeleteMessagePayload {
  messageId: string;       // Required, UUID v4
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('chat.message.delete', {
  messageId: 'msg_abc123',
  idempotencyKey: uuidv4()
});
```

**Broadcast Event:** `chat.message.deleted`

```typescript
socket.on('chat.message.deleted', (data: { messageId: string }) => {
  // Remove message from UI
  setChatMessages(prev => prev.filter(m => m.id !== data.messageId));
});
```

### 4.5 React to Message

**Event:** `chat.message.react`
**Direction:** Client → Server
**Behavior:** Toggle - sending the same emoji again removes the reaction

```typescript
interface ReactToMessagePayload {
  messageId: string;       // Required, UUID v4
  emoji: string;           // Required, max 8 characters (for complex emojis)
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('chat.message.react', {
  messageId: 'msg_abc123',
  emoji: '👍',
  idempotencyKey: uuidv4()
});
```

**Broadcast Event:** `chat.message.updated` (same as edit)

The updated message will include `reactionsSummary`:

```typescript
{
  id: 'msg_abc123',
  // ... other fields
  reactionsSummary: {
    '👍': 5,
    '❤️': 2,
    '🔥': 1
  }
}
```

---

## 5. Polls Feature

Create and manage live polls during sessions. Supports voting, closing, and giveaways.

### 5.1 Create Poll

**Event:** `poll.create`
**Direction:** Client → Server
**Permission:** `poll:create`

```typescript
interface CreatePollPayload {
  question: string;        // Required, max 500 characters
  options: Array<{
    text: string;          // Required, max 200 characters per option
  }>;                      // Minimum 2 options required
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('poll.create', {
  question: 'What topic should we cover next?',
  options: [
    { text: 'React Performance' },
    { text: 'TypeScript Advanced' },
    { text: 'Testing Strategies' }
  ],
  idempotencyKey: uuidv4()
}, (response) => {
  if (response.success) {
    console.log('Poll created:', response.pollId);
  }
});
```

### 5.2 Poll Opened (Broadcast)

**Event:** `poll.opened`
**Direction:** Server → Client
**Room:** `session:{sessionId}`

```typescript
interface Poll {
  id: string;
  question: string;
  isActive: boolean;
  creatorId: string;
  sessionId: string;
  options: Array<{
    id: string;
    text: string;
  }>;
  creator: {
    id: string;
    firstName: string;
    lastName: string;
  };
}

socket.on('poll.opened', (poll: Poll) => {
  // Display poll modal/card to users
  setActivePoll(poll);
  setShowPollModal(true);
});
```

### 5.3 Submit Vote

**Event:** `poll.vote.submit`
**Direction:** Client → Server
**Constraint:** Can only vote once per poll

```typescript
interface SubmitVotePayload {
  pollId: string;          // Required, UUID v4
  optionId: string;        // Required, UUID v4
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('poll.vote.submit', {
  pollId: 'poll_abc123',
  optionId: 'opt_xyz789',
  idempotencyKey: uuidv4()
}, (response) => {
  if (response.success) {
    console.log('Vote submitted');
  } else {
    // Handle "You have already voted" error
    console.error(response.error);
  }
});
```

### 5.4 Poll Results Updated (Broadcast)

**Event:** `poll.results.updated`
**Direction:** Server → Client
**Room:** `session:{sessionId}`

```typescript
interface PollResults {
  poll: {
    id: string;
    question: string;
    isActive: boolean;
    sessionId: string;
    options: Array<{
      id: string;
      text: string;
      voteCount: number;
    }>;
    totalVotes: number;
  };
  userVotedForOptionId: string | null;  // The current user's vote (null if not voted)
}

socket.on('poll.results.updated', (data: PollResults) => {
  // Update poll results UI with vote counts
  setActivePoll(data.poll);
  setUserVote(data.userVotedForOptionId);
});
```

### 5.5 Close Poll

**Event:** `poll.manage`
**Direction:** Client → Server
**Permission:** `poll:manage`

```typescript
interface ManagePollPayload {
  pollId: string;          // Required, UUID v4
  action: 'close';         // Only 'close' supported currently
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('poll.manage', {
  pollId: 'poll_abc123',
  action: 'close',
  idempotencyKey: uuidv4()
});
```

**Broadcast Event:** `poll.closed`

```typescript
socket.on('poll.closed', (finalResults: PollResults) => {
  // Show final results, disable voting UI
  setActivePoll({ ...finalResults.poll, isActive: false });
  setShowFinalResults(true);
});
```

### 5.6 Start Giveaway

**Event:** `poll.giveaway.start`
**Direction:** Client → Server
**Permission:** `poll:manage`

Select a random winner from users who voted for a specific option.

```typescript
interface StartGiveawayPayload {
  pollId: string;          // Required, UUID v4
  winningOptionId: string; // Required, UUID v4 - the "correct answer"
  prize: string;           // Required, max 255 characters
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('poll.giveaway.start', {
  pollId: 'poll_abc123',
  winningOptionId: 'opt_xyz789',  // Users who voted for this option are eligible
  prize: 'Free conference ticket!',
  idempotencyKey: uuidv4()
});
```

**Broadcast Event:** `poll.giveaway.winner`

```typescript
interface GiveawayWinner {
  pollId: string;
  winner: {
    id: string;
    firstName: string;
    lastName: string;
  };
  prize: string;
}

socket.on('poll.giveaway.winner', (data: GiveawayWinner) => {
  // Display winner announcement with confetti!
  showWinnerModal(data);
});
```

---

## 6. Q&A Feature

Audience Q&A with moderation, upvoting, answering, and tagging.

### 6.1 Ask Question

**Event:** `qa.question.ask`
**Direction:** Client → Server
**Permission:** None

```typescript
interface AskQuestionPayload {
  text: string;            // Required, max 500 characters
  isAnonymous?: boolean;   // Optional, default false
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('qa.question.ask', {
  text: 'How do you handle state management in large applications?',
  isAnonymous: false,
  idempotencyKey: uuidv4()
}, (response) => {
  if (response.success) {
    console.log('Question submitted:', response.questionId);
  }
});
```

### 6.2 New Question (Broadcast)

**Event:** `qa.question.new`
**Direction:** Server → Client
**Room:** `session:{sessionId}` and `session:{sessionId}:moderation`

```typescript
interface Question {
  id: string;
  text: string;
  isAnonymous: boolean;
  status: 'pending' | 'approved' | 'dismissed';
  createdAt: string;
  authorId: string;
  authorEmail: string;
  sessionId: string;
  answer?: {
    text: string;
    answeredAt: string;
    answeredById: string;
  };
  tags?: string[];
  _count: {
    upvotes: number;
  };
}

socket.on('qa.question.new', (question: Question) => {
  // Add to Q&A list
  setQuestions(prev => [question, ...prev]);
});
```

### 6.3 Upvote Question

**Event:** `qna.question.upvote`
**Direction:** Client → Server
**Behavior:** Toggle - upvoting again removes the upvote

```typescript
interface UpvoteQuestionPayload {
  questionId: string;      // Required, UUID v4
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('qna.question.upvote', {
  questionId: 'q_abc123',
  idempotencyKey: uuidv4()
}, (response) => {
  // response includes: { success, questionId, upvotes }
});
```

**Broadcast Event:** `qna.question.updated`

```typescript
socket.on('qna.question.updated', (question: Question) => {
  setQuestions(prev =>
    prev.map(q => q.id === question.id ? question : q)
  );
});
```

### 6.4 Moderate Question

**Event:** `qna.question.moderate`
**Direction:** Client → Server
**Permission:** `qna:moderate`

```typescript
interface ModerateQuestionPayload {
  questionId: string;           // Required, UUID v4
  status: 'approved' | 'dismissed';  // Required
  moderatorNote?: string;       // Optional, max 200 characters
  idempotencyKey: string;       // Required, UUID v4
}

socket.emit('qna.question.moderate', {
  questionId: 'q_abc123',
  status: 'approved',
  moderatorNote: 'Great question!',
  idempotencyKey: uuidv4()
});
```

**Broadcast Events:**
- `qna.question.updated` → Moderation room + Public (if approved)
- `qna.question.removed` → Public room (if dismissed)

```typescript
socket.on('qna.question.removed', (data: { questionId: string }) => {
  setQuestions(prev => prev.filter(q => q.id !== data.questionId));
});
```

### 6.5 Answer Question

**Event:** `qna.question.answer`
**Direction:** Client → Server
**Permission:** `qna:moderate`

```typescript
interface AnswerQuestionPayload {
  questionId: string;      // Required, UUID v4
  answerText: string;      // Required, max 2000 characters, must have non-whitespace
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('qna.question.answer', {
  questionId: 'q_abc123',
  answerText: 'Great question! The best approach is...',
  idempotencyKey: uuidv4()
});
```

The updated question (via `qna.question.updated`) will include the `answer` field.

### 6.6 Tag Question

**Event:** `qna.question.tag`
**Direction:** Client → Server
**Permission:** `qna:moderate`

```typescript
interface TagQuestionPayload {
  questionId: string;      // Required, UUID v4
  tags: string[];          // Required, array of tag strings
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('qna.question.tag', {
  questionId: 'q_abc123',
  tags: ['react', 'performance', 'featured'],
  idempotencyKey: uuidv4()
});
```

### 6.7 Moderation Alert

**Event:** `moderation.alert`
**Direction:** Server → Client
**Room:** `session:{sessionId}:moderation` (moderators only)

```typescript
socket.on('moderation.alert', (payload: any) => {
  // Show alert in moderation panel
  showModerationNotification(payload);
});
```

---

## 7. Direct Messaging

Private messaging between users with delivery and read receipts.

### 7.1 Send DM

**Event:** `dm.send`
**Direction:** Client → Server

```typescript
interface SendDmPayload {
  recipientId: string;     // Required, UUID v4 - the user to message
  text: string;            // Required, max 2000 characters
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('dm.send', {
  recipientId: 'user_xyz789',
  text: 'Hey! Great talk. Would love to connect.',
  idempotencyKey: uuidv4()
}, (response) => {
  if (response.success) {
    // Optimistically add to conversation
    addMessageToConversation({
      id: response.messageId,
      timestamp: response.timestamp,
      // ... other fields
    });
  }
});
```

### 7.2 Receive DM

**Event:** `dm.new`
**Direction:** Server → Client
**Room:** `user:{userId}` (auto-joined)

```typescript
interface DirectMessage {
  id: string;
  text: string;
  timestamp: string;
  senderId: string;
  conversationId: string;
  isDelivered: boolean;
  isRead: boolean;
}

socket.on('dm.new', (message: DirectMessage) => {
  // Add to conversation UI
  addMessageToConversation(message);

  // If conversation is open, send delivery receipt
  if (isConversationOpen(message.conversationId)) {
    socket.emit('dm.delivered', {
      messageId: message.id,
      idempotencyKey: uuidv4()
    });
  }
});
```

### 7.3 Mark as Delivered

**Event:** `dm.delivered`
**Direction:** Client → Server

Send this when you receive a DM (the message has been delivered to the client).

```typescript
interface DeliveryReceiptPayload {
  messageId: string;       // Required, UUID v4
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('dm.delivered', {
  messageId: 'dm_abc123',
  idempotencyKey: uuidv4()
});
```

**Event to Original Sender:** `dm.delivery_update`

```typescript
socket.on('dm.delivery_update', (data: {
  messageId: string;
  conversationId: string;
  isDelivered: boolean;
  deliveredAt: string;
}) => {
  // Show single checkmark ✓
  updateMessageStatus(data.messageId, 'delivered');
});
```

### 7.4 Mark as Read

**Event:** `dm.read`
**Direction:** Client → Server

Send this when the user actually sees/reads the message.

```typescript
interface ReadReceiptPayload {
  messageId: string;       // Required, UUID v4
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('dm.read', {
  messageId: 'dm_abc123',
  idempotencyKey: uuidv4()
});
```

**Event to Original Sender:** `dm.read_update`

```typescript
socket.on('dm.read_update', (data: {
  messageId: string;
  conversationId: string;
  isRead: boolean;
  readAt: string;
}) => {
  // Show double checkmark ✓✓
  updateMessageStatus(data.messageId, 'read');
});
```

### 7.5 Edit DM

**Event:** `dm.message.edit`
**Direction:** Client → Server

```typescript
interface EditDmPayload {
  messageId: string;       // Required, UUID v4
  newText: string;         // Required, max 2000 characters
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('dm.message.edit', {
  messageId: 'dm_abc123',
  newText: 'Updated message',
  idempotencyKey: uuidv4()
});
```

**Broadcast Event:** `dm.message.updated` (to all conversation participants)

### 7.6 Delete DM

**Event:** `dm.message.delete`
**Direction:** Client → Server

```typescript
interface DeleteDmPayload {
  messageId: string;       // Required, UUID v4
  idempotencyKey: string;  // Required, UUID v4
}

socket.emit('dm.message.delete', {
  messageId: 'dm_abc123',
  idempotencyKey: uuidv4()
});
```

**Broadcast Event:** `dm.message.deleted` (to all conversation participants)

---

## 8. Emoji Reactions

Floating emoji reactions during live sessions (like Instagram Live or Twitch).

### 8.1 Send Reaction

**Event:** `reaction.send`
**Direction:** Client → Server

```typescript
interface SendReactionPayload {
  emoji: string;  // Must be from the allowed list
}

socket.emit('reaction.send', {
  emoji: '🔥'
});

// No direct response - reactions are batched and broadcast
```

### 8.2 Receive Reaction Burst

**Event:** `reaction.burst`
**Direction:** Server → Client
**Broadcast:** Every 2 seconds if reactions exist

```typescript
// Server broadcasts aggregated reaction counts
socket.on('reaction.burst', (counts: Record<string, number>) => {
  // Example: { "🔥": 15, "👏": 8, "❤️": 3 }

  // Animate floating emojis based on counts
  Object.entries(counts).forEach(([emoji, count]) => {
    for (let i = 0; i < Math.min(count, 10); i++) {
      spawnFloatingEmoji(emoji);
    }
  });
});
```

### 8.3 Allowed Emojis

Only these emojis are accepted:

```typescript
const ALLOWED_EMOJIS = [
  '👍',  // Approval or agreement
  '❤️',  // Love or appreciation
  '🎉',  // Celebration
  '💡',  // Idea or suggestion
  '😂',  // Laughter
  '👏',  // Applause
  '🔥',  // Excitement or highlight
  '🙏',  // Gratitude or thanks
  '🤝',  // Partnership or networking
  '🚀',  // Progress or launch
  '🙌',  // Support or encouragement
  '✅',  // Confirmation or success
  '🎶',  // Music vibes
  '🕺',  // Dancing or good vibes
  '📢',  // Announcements, engagement
  '📸',  // Photo moments
  '🌍',  // Global presence
  '🧠',  // Smart insight
];
```

### 8.4 Mood Analytics

**Event:** `mood.analytics.updated`
**Direction:** Server → Client

```typescript
socket.on('mood.analytics.updated', (analytics: any) => {
  // Display mood/sentiment visualization
  updateMoodChart(analytics);
});
```

### Example: Reaction Button Component

```tsx
const ReactionButton = ({ emoji }: { emoji: string }) => {
  const handleClick = () => {
    socket.emit('reaction.send', { emoji });
    // Animate the button
    triggerButtonAnimation();
  };

  return (
    <button onClick={handleClick} className="reaction-btn">
      {emoji}
    </button>
  );
};

// Reaction bar with all emojis
const ReactionBar = () => (
  <div className="reaction-bar">
    {ALLOWED_EMOJIS.slice(0, 6).map(emoji => (
      <ReactionButton key={emoji} emoji={emoji} />
    ))}
  </div>
);
```

---

## 9. Gamification

Points, leaderboards, and achievements to drive engagement.

### 9.1 Request Leaderboard

**Event:** `leaderboard.request`
**Direction:** Client → Server

```typescript
socket.emit('leaderboard.request', null, (response) => {
  if (response.success) {
    setLeaderboard(response.data);
  }
});

// Response structure
interface LeaderboardResponse {
  success: boolean;
  event: 'leaderboard.data';
  data: {
    topEntries: Array<{
      rank: number;
      user: {
        id: string;
        firstName: string;
        lastName: string;
      };
      score: number;
    }>;
    currentUser: {
      rank: number | null;  // null if not on leaderboard yet
      score: number;
    } | null;
  };
  error?: string;
}
```

### 9.2 Leaderboard Updated (Broadcast)

**Event:** `leaderboard.updated`
**Direction:** Server → Client
**Room:** `session:{sessionId}`

```typescript
socket.on('leaderboard.updated', (data: {
  topEntries: Array<{
    rank: number;
    user: { id: string; firstName: string; lastName: string };
    score: number;
  }>;
}) => {
  // Update leaderboard display
  setLeaderboard(prev => ({ ...prev, topEntries: data.topEntries }));
});
```

### 9.3 Team Leaderboard Updated

**Event:** `team.leaderboard.updated`
**Direction:** Server → Client
**Room:** `session:{sessionId}`

```typescript
socket.on('team.leaderboard.updated', (data: {
  teamScores: Array<{
    rank: number;
    teamId: string;
    name: string;
    memberCount: number;
    score: number;
  }>;
}) => {
  setTeamLeaderboard(data.teamScores);
});
```

### 9.4 Achievement Unlocked

**Event:** `achievement.unlocked`
**Direction:** Server → Client
**Room:** `user:{userId}` (private)

```typescript
interface Achievement {
  id: string;
  badgeName: string;
  description: string;
  unlockedAt: string;
}

socket.on('achievement.unlocked', (achievement: Achievement) => {
  // Show achievement popup/toast with animation
  showAchievementToast(achievement);
});
```

### 9.5 Points Awarded

**Event:** `gamification.points.awarded`
**Direction:** Server → Client
**Room:** `user:{userId}` (private)

```typescript
interface PointsAwardedPayload {
  points: number;
  reason: PointReason;
  newTotalScore: number;
}

type PointReason =
  | 'MESSAGE_SENT'
  | 'MESSAGE_REACTED'
  | 'QUESTION_ASKED'
  | 'QUESTION_UPVOTED'
  | 'POLL_CREATED'
  | 'POLL_VOTED'
  | 'WAITLIST_JOINED';

socket.on('gamification.points.awarded', (data: PointsAwardedPayload) => {
  // Show "+5 points" animation
  showPointsAnimation(data.points);
  // Update total score display
  setUserScore(data.newTotalScore);
});
```

### 9.6 Point Values Reference

| Action | Points |
|--------|--------|
| MESSAGE_SENT | 1 |
| MESSAGE_REACTED | 2 |
| QUESTION_ASKED | 5 |
| QUESTION_UPVOTED | 2 |
| POLL_CREATED | 10 |
| POLL_VOTED | 1 |
| WAITLIST_JOINED | 3 |

### 9.7 Achievements Reference

| Achievement | Badge Name | Trigger | Condition |
|-------------|------------|---------|-----------|
| First Question | "Question Asker" | QUESTION_ASKED | Ask 1 question |
| Score 50 | "Engaged Attendee" | POINTS_TOTAL | Reach 50 points |
| Super Voter | "Super Voter" | POLL_VOTED | Vote 5 times |

---

## 10. Live Dashboard

Real-time metrics for event admins.

### 10.1 Join Dashboard

**Event:** `dashboard.join`
**Direction:** Client → Server
**Permission:** `dashboard:read:live`

```typescript
socket.emit('dashboard.join', null, (response) => {
  if (response.success) {
    console.log('Joined dashboard');
  } else {
    console.error('Failed to join:', response.error);
  }
});
```

### 10.2 Dashboard Update

**Event:** `dashboard.update`
**Direction:** Server → Client
**Broadcast:** Every 5 seconds while admins are connected

```typescript
interface DashboardData {
  totalMessages: number;
  pollVotes: number;
  questionsAsked: number;
  questionUpvotes: number;
  reactions: number;
  recentCheckIns: Array<{
    name: string;
    timestamp: string;
  }>;
}

socket.on('dashboard.update', (data: DashboardData) => {
  setDashboardStats(data);
});
```

### 10.3 Capacity Update

**Event:** `dashboard.capacity.updated`
**Direction:** Server → Client

```typescript
socket.on('dashboard.capacity.updated', (data: {
  eventId: string;
  resourceId: string;
  currentCount: number;
  maxCapacity: number;
}) => {
  // Update capacity indicator
  const percentage = (data.currentCount / data.maxCapacity) * 100;
  setCapacityPercentage(percentage);
});
```

### 10.4 System Metrics

**Event:** `dashboard.metrics.updated`
**Direction:** Server → Client

```typescript
socket.on('dashboard.metrics.updated', (payload: {
  orgId: string;
  metrics: object;
}) => {
  setSystemMetrics(payload.metrics);
});
```

---

## 11. Notifications

Push notifications for various events.

### 11.1 Session Reminder

**Event:** `notification.session_reminder`
**Direction:** Server → Client
**Room:** `user:{userId}`

```typescript
socket.on('notification.session_reminder', (data: {
  sessionId: string;
  sessionTitle: string;
  startsIn: number;  // minutes
}) => {
  showToast({
    title: 'Session Starting Soon',
    message: `"${data.sessionTitle}" starts in ${data.startsIn} minutes`,
    action: () => navigateToSession(data.sessionId)
  });
});
```

### 11.2 Personal Notification

**Event:** `notification.personal`
**Direction:** Server → Client
**Room:** `user:{userId}`

```typescript
socket.on('notification.personal', (data: {
  type: string;
  title: string;
  message: string;
  actionUrl?: string;
}) => {
  showNotification(data);
});
```

### 11.3 Emergency Alert

**Event:** `notification.emergency`
**Direction:** Server → Client
**Room:** `event:{eventId}`

```typescript
socket.on('notification.emergency', (data: {
  alertType: string;
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
}) => {
  // Show prominent alert that can't be dismissed easily
  showEmergencyAlert(data);
});
```

### 11.4 Schedule Change

**Event:** `notification.schedule_change`
**Direction:** Server → Client
**Room:** `event:{eventId}`

```typescript
socket.on('notification.schedule_change', (data: {
  changeType: 'time_change' | 'room_change' | 'cancelled' | 'added';
  sessionId: string;
  sessionTitle: string;
  oldValue?: string;
  newValue?: string;
}) => {
  showToast({
    title: 'Schedule Updated',
    message: `${data.sessionTitle}: ${data.changeType}`,
    type: data.changeType === 'cancelled' ? 'warning' : 'info'
  });
});
```

---

## 12. Content/Presentation Control

Control presentations and share content during live sessions.

### 12.1 Join Session

**Event:** `session.join`
**Direction:** Client → Server

```typescript
socket.emit('session.join', { sessionId: 'sess_abc123' });
```

### 12.2 Leave Session

**Event:** `session.leave`
**Direction:** Client → Server

```typescript
socket.emit('session.leave', { sessionId: 'sess_abc123' });
```

### 12.3 Control Presentation

**Event:** `content.control`
**Direction:** Client → Server
**Permission:** `content:manage`

```typescript
type ContentAction = 'NEXT_SLIDE' | 'PREV_SLIDE' | 'GO_TO_SLIDE' | 'START' | 'STOP';

interface ContentControlPayload {
  sessionId: string;
  action: ContentAction;
  targetSlide?: number;  // Required for GO_TO_SLIDE
}

// Next slide
socket.emit('content.control', {
  sessionId: 'sess_abc123',
  action: 'NEXT_SLIDE'
}, (response) => {
  if (response.success) {
    console.log('Now on slide:', response.newState.currentSlide);
  }
});

// Go to specific slide
socket.emit('content.control', {
  sessionId: 'sess_abc123',
  action: 'GO_TO_SLIDE',
  targetSlide: 5
});
```

### 12.4 Slide Update (Broadcast)

**Event:** `slide.update`
**Direction:** Server → Client
**Room:** `session:{sessionId}`

```typescript
interface SlideState {
  currentSlide: number;
  totalSlides: number;
  isActive: boolean;
}

socket.on('slide.update', (state: SlideState) => {
  setCurrentSlide(state.currentSlide);
  setTotalSlides(state.totalSlides);
  setPresentationActive(state.isActive);
});
```

### 12.5 Request Current State

**Event:** `content.request_state`
**Direction:** Client → Server

Use this when a user joins mid-presentation to sync their view.

```typescript
socket.emit('content.request_state', { sessionId: 'sess_abc123' }, (response) => {
  if (response.success && response.state) {
    setCurrentSlide(response.state.currentSlide);
    setTotalSlides(response.state.totalSlides);
    setSlideUrls(response.state.slideUrls);
  }
});
```

### 12.6 Content Drop

**Event:** `content.drop`
**Direction:** Client → Server
**Permission:** `content:manage`

Share a link, file, or resource with all attendees.

```typescript
interface DropContentPayload {
  type: 'LINK' | 'FILE' | 'RESOURCE';
  title: string;
  url: string;
  description?: string;
}

socket.emit('content.drop', {
  type: 'LINK',
  title: 'Presentation Slides',
  url: 'https://example.com/slides.pdf',
  description: 'Download the full slides here'
});
```

**Broadcast Event:** `content.dropped`

```typescript
socket.on('content.dropped', (data: {
  type: string;
  title: string;
  url: string;
  description?: string;
  droppedBy: {
    id: string;
    name: string;
  };
  timestamp: string;
}) => {
  // Show content drop notification with download link
  showContentDrop(data);
});
```

### 12.7 Presentation Status Update

**Event:** `presentation.status.update`
**Direction:** Server → Client
**Room:** `user:{userId}` (sent to the uploader)

```typescript
socket.on('presentation.status.update', (data: {
  sessionId: string;
  status: 'processing' | 'ready' | 'failed';
}) => {
  if (data.status === 'ready') {
    showToast({ message: 'Presentation ready!' });
    refreshPresentationData(data.sessionId);
  } else if (data.status === 'failed') {
    showError({ message: 'Presentation processing failed' });
  }
});
```

---

## 13. Agenda Updates

Real-time schedule/agenda changes.

### 13.1 Agenda Update

**Event:** `agenda.update`
**Direction:** Server → Client
**Room:** `event:{eventId}`

```typescript
interface AgendaUpdatePayload {
  eventId: string;
  updateType: 'CREATED' | 'UPDATED' | 'DELETED';
  session: {
    id: string;
    title: string;
    startTime: string;
    endTime: string;
    // ... other session fields
  };
}

socket.on('agenda.update', (payload: AgendaUpdatePayload) => {
  switch (payload.updateType) {
    case 'CREATED':
      addSessionToAgenda(payload.session);
      break;
    case 'UPDATED':
      updateSessionInAgenda(payload.session);
      break;
    case 'DELETED':
      removeSessionFromAgenda(payload.session.id);
      break;
  }
});
```

---

## 14. Permissions Reference

### Permission Strings

The user's permissions are included in their JWT and validated by the backend.

| Permission | Required For |
|------------|--------------|
| `poll:create` | Creating polls |
| `poll:manage` | Closing polls, starting giveaways |
| `qna:moderate` | Approving/dismissing questions, answering, tagging |
| `chat:delete:own` | Deleting own chat messages |
| `chat:delete:any` | Deleting any chat message (moderator) |
| `content:manage` | Controlling presentations, dropping content |
| `dashboard:read:live` | Viewing live dashboard |

### Checking Permissions in Frontend

```typescript
// Get permissions from auth context/store
const { user } = useAuth();
const permissions = user?.permissions || [];

// Check specific permission
const canCreatePoll = permissions.includes('poll:create');
const canModerateQA = permissions.includes('qna:moderate');
const canManageContent = permissions.includes('content:manage');

// Conditional UI rendering
{canCreatePoll && (
  <Button onClick={openCreatePollModal}>Create Poll</Button>
)}

{canModerateQA && (
  <ModerationPanel questions={pendingQuestions} />
)}
```

### Role-Based Permission Mapping (Typical)

| Role | Permissions |
|------|-------------|
| OWNER | All permissions |
| ADMIN | All except some org-level actions |
| MEMBER | `chat:delete:own` |
| MODERATOR | `qna:moderate`, `chat:delete:any`, `poll:manage` |
| SPEAKER | `content:manage`, `poll:create` |

---

## 15. Error Handling

### Standard Error Response

All events return responses in this format:

```typescript
interface SuccessResponse {
  success: true;
  [key: string]: any;  // Additional data
}

interface ErrorResponse {
  success: false;
  error: string | {
    message: string;
    statusCode: number;
  };
}

type Response = SuccessResponse | ErrorResponse;
```

### Common Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Duplicate request` | Same idempotencyKey used twice | Generate new UUID for each request |
| `You do not have permission` | Missing required permission | Check user permissions, hide UI |
| `Poll is no longer active` | Voting on closed poll | Refresh poll state, disable voting |
| `Messages can only be edited within 5 minutes` | Edit window expired | Show error, disable edit button |
| `You can only edit your own messages` | Trying to edit others' messages | UI should prevent this |
| `You have already voted in this poll` | Double voting | Track user's vote, disable button |
| `Session ID is required` | Missing sessionId in query | Ensure sessionId is passed |
| `Authentication failed` | Invalid/expired JWT | Refresh token and reconnect |

### Error Handling Pattern

```typescript
socket.emit('poll.vote.submit', {
  pollId,
  optionId,
  idempotencyKey: uuidv4()
}, (response) => {
  if (response.success) {
    // Handle success
    setUserVote(optionId);
  } else {
    // Handle error
    const errorMessage = typeof response.error === 'string'
      ? response.error
      : response.error.message;

    showToast({ type: 'error', message: errorMessage });

    // Specific error handling
    if (errorMessage.includes('already voted')) {
      setAlreadyVoted(true);
    }
  }
});
```

### Idempotency Keys

**CRITICAL:** Every mutation requires a UUID v4 idempotency key.

```typescript
import { v4 as uuidv4 } from 'uuid';

// Generate fresh UUID for each request
socket.emit('chat.message.send', {
  text: 'Hello!',
  idempotencyKey: uuidv4()  // Always generate new
});

// WRONG - Don't reuse keys
const key = uuidv4();
socket.emit('chat.message.send', { text: 'First', idempotencyKey: key });
socket.emit('chat.message.send', { text: 'Second', idempotencyKey: key }); // Will fail!
```

---

## 16. TypeScript Interfaces

Complete TypeScript interfaces for all payloads:

```typescript
// ============ CHAT ============
interface SendMessagePayload {
  text: string;
  idempotencyKey: string;
  replyingToMessageId?: string;
}

interface EditMessagePayload {
  messageId: string;
  newText: string;
  idempotencyKey: string;
}

interface DeleteMessagePayload {
  messageId: string;
  idempotencyKey: string;
}

interface ReactToMessagePayload {
  messageId: string;
  emoji: string;
  idempotencyKey: string;
}

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
  reactionsSummary?: Record<string, number>;
}

// ============ POLLS ============
interface CreatePollPayload {
  question: string;
  options: Array<{ text: string }>;
  idempotencyKey: string;
}

interface SubmitVotePayload {
  pollId: string;
  optionId: string;
  idempotencyKey: string;
}

interface ManagePollPayload {
  pollId: string;
  action: 'close';
  idempotencyKey: string;
}

interface StartGiveawayPayload {
  pollId: string;
  winningOptionId: string;
  prize: string;
  idempotencyKey: string;
}

interface Poll {
  id: string;
  question: string;
  isActive: boolean;
  creatorId: string;
  sessionId: string;
  options: Array<{
    id: string;
    text: string;
    voteCount?: number;
  }>;
  totalVotes?: number;
  creator?: {
    id: string;
    firstName: string;
    lastName: string;
  };
}

interface PollResults {
  poll: Poll;
  userVotedForOptionId: string | null;
}

// ============ Q&A ============
interface AskQuestionPayload {
  text: string;
  isAnonymous?: boolean;
  idempotencyKey: string;
}

interface UpvoteQuestionPayload {
  questionId: string;
  idempotencyKey: string;
}

interface ModerateQuestionPayload {
  questionId: string;
  status: 'approved' | 'dismissed';
  moderatorNote?: string;
  idempotencyKey: string;
}

interface AnswerQuestionPayload {
  questionId: string;
  answerText: string;
  idempotencyKey: string;
}

interface TagQuestionPayload {
  questionId: string;
  tags: string[];
  idempotencyKey: string;
}

interface Question {
  id: string;
  text: string;
  isAnonymous: boolean;
  status: 'pending' | 'approved' | 'dismissed';
  createdAt: string;
  authorId: string;
  authorEmail: string;
  sessionId: string;
  answer?: {
    text: string;
    answeredAt: string;
    answeredById: string;
  };
  tags?: string[];
  _count: {
    upvotes: number;
  };
}

// ============ DIRECT MESSAGING ============
interface SendDmPayload {
  recipientId: string;
  text: string;
  idempotencyKey: string;
}

interface DeliveryReceiptPayload {
  messageId: string;
  idempotencyKey: string;
}

interface ReadReceiptPayload {
  messageId: string;
  idempotencyKey: string;
}

interface EditDmPayload {
  messageId: string;
  newText: string;
  idempotencyKey: string;
}

interface DeleteDmPayload {
  messageId: string;
  idempotencyKey: string;
}

interface DirectMessage {
  id: string;
  text: string;
  timestamp: string;
  senderId: string;
  conversationId: string;
  isDelivered: boolean;
  isRead: boolean;
}

// ============ REACTIONS ============
interface SendReactionPayload {
  emoji: string;
}

// ============ GAMIFICATION ============
interface LeaderboardEntry {
  rank: number;
  user: {
    id: string;
    firstName: string;
    lastName: string;
  };
  score: number;
}

interface LeaderboardData {
  topEntries: LeaderboardEntry[];
  currentUser: {
    rank: number | null;
    score: number;
  } | null;
}

interface Achievement {
  id: string;
  badgeName: string;
  description: string;
  unlockedAt: string;
}

type PointReason =
  | 'MESSAGE_SENT'
  | 'MESSAGE_REACTED'
  | 'QUESTION_ASKED'
  | 'QUESTION_UPVOTED'
  | 'POLL_CREATED'
  | 'POLL_VOTED'
  | 'WAITLIST_JOINED';

interface PointsAwardedPayload {
  points: number;
  reason: PointReason;
  newTotalScore: number;
}

// ============ CONTENT CONTROL ============
type ContentAction = 'NEXT_SLIDE' | 'PREV_SLIDE' | 'GO_TO_SLIDE' | 'START' | 'STOP';

interface ContentControlPayload {
  sessionId: string;
  action: ContentAction;
  targetSlide?: number;
}

interface SlideState {
  currentSlide: number;
  totalSlides: number;
  isActive: boolean;
}

interface DropContentPayload {
  type: 'LINK' | 'FILE' | 'RESOURCE';
  title: string;
  url: string;
  description?: string;
}

// ============ NOTIFICATIONS ============
interface SessionReminderPayload {
  sessionId: string;
  sessionTitle: string;
  startsIn: number;
}

interface PersonalNotificationPayload {
  type: string;
  title: string;
  message: string;
  actionUrl?: string;
}

interface EmergencyAlertPayload {
  alertType: string;
  message: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  timestamp: string;
}

interface ScheduleChangePayload {
  changeType: 'time_change' | 'room_change' | 'cancelled' | 'added';
  sessionId: string;
  sessionTitle: string;
  oldValue?: string;
  newValue?: string;
}

// ============ DASHBOARD ============
interface DashboardData {
  totalMessages: number;
  pollVotes: number;
  questionsAsked: number;
  questionUpvotes: number;
  reactions: number;
  recentCheckIns: Array<{
    name: string;
    timestamp: string;
  }>;
}

// ============ AGENDA ============
interface AgendaUpdatePayload {
  eventId: string;
  updateType: 'CREATED' | 'UPDATED' | 'DELETED';
  session: {
    id: string;
    title: string;
    startTime: string;
    endTime: string;
  };
}
```

---

## 17. Quick Start Example

Complete example of setting up real-time features in a React app:

```typescript
// hooks/useSocket.ts
import { useEffect, useRef, useCallback } from 'react';
import { io, Socket } from 'socket.io-client';
import { v4 as uuidv4 } from 'uuid';
import { useAuth } from './useAuth';

const SOCKET_URL = process.env.NEXT_PUBLIC_REALTIME_URL || 'http://localhost:3002';

export function useSocket(sessionId?: string) {
  const { accessToken, user } = useAuth();
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    if (!accessToken) return;

    const socket = io(`${SOCKET_URL}/events`, {
      auth: { token: `Bearer ${accessToken}` },
      query: sessionId ? { sessionId } : {},
      transports: ['websocket'],
      reconnection: true,
    });

    socket.on('connectionAcknowledged', ({ userId }) => {
      console.log('Connected:', userId);
      if (sessionId) {
        socket.emit('session.join', { sessionId });
      }
    });

    socket.on('systemError', (error) => {
      console.error('Socket error:', error);
    });

    socketRef.current = socket;

    return () => {
      if (sessionId) {
        socket.emit('session.leave', { sessionId });
      }
      socket.disconnect();
    };
  }, [accessToken, sessionId]);

  const sendMessage = useCallback((text: string, replyTo?: string) => {
    socketRef.current?.emit('chat.message.send', {
      text,
      idempotencyKey: uuidv4(),
      replyingToMessageId: replyTo,
    });
  }, []);

  const vote = useCallback((pollId: string, optionId: string) => {
    socketRef.current?.emit('poll.vote.submit', {
      pollId,
      optionId,
      idempotencyKey: uuidv4(),
    });
  }, []);

  const askQuestion = useCallback((text: string, anonymous = false) => {
    socketRef.current?.emit('qa.question.ask', {
      text,
      isAnonymous: anonymous,
      idempotencyKey: uuidv4(),
    });
  }, []);

  const sendReaction = useCallback((emoji: string) => {
    socketRef.current?.emit('reaction.send', { emoji });
  }, []);

  return {
    socket: socketRef.current,
    sendMessage,
    vote,
    askQuestion,
    sendReaction,
  };
}

// components/ChatPanel.tsx
import { useEffect, useState } from 'react';
import { useSocket } from '../hooks/useSocket';
import type { ChatMessage } from '../types/realtime';

export function ChatPanel({ sessionId }: { sessionId: string }) {
  const { socket, sendMessage } = useSocket(sessionId);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');

  useEffect(() => {
    if (!socket) return;

    socket.on('chat.message.new', (message: ChatMessage) => {
      setMessages(prev => [...prev, message]);
    });

    socket.on('chat.message.updated', (message: ChatMessage) => {
      setMessages(prev => prev.map(m => m.id === message.id ? message : m));
    });

    socket.on('chat.message.deleted', ({ messageId }) => {
      setMessages(prev => prev.filter(m => m.id !== messageId));
    });

    return () => {
      socket.off('chat.message.new');
      socket.off('chat.message.updated');
      socket.off('chat.message.deleted');
    };
  }, [socket]);

  const handleSend = () => {
    if (input.trim()) {
      sendMessage(input);
      setInput('');
    }
  };

  return (
    <div className="chat-panel">
      <div className="messages">
        {messages.map(msg => (
          <div key={msg.id} className="message">
            <strong>{msg.author.firstName}:</strong> {msg.text}
            {msg.reactionsSummary && (
              <div className="reactions">
                {Object.entries(msg.reactionsSummary).map(([emoji, count]) => (
                  <span key={emoji}>{emoji} {count}</span>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Type a message..."
        />
        <button onClick={handleSend}>Send</button>
      </div>
    </div>
  );
}
```

---

## Summary Table

| Feature | Client Events | Server Events | Status |
|---------|--------------|---------------|--------|
| **Chat** | 4 | 3 | Ready |
| **Polls** | 4 | 4 | Ready |
| **Q&A** | 5 | 4 | Ready |
| **Direct Messaging** | 5 | 4 | Ready |
| **Emoji Reactions** | 1 | 2 | Ready |
| **Gamification** | 1 | 4 | Ready |
| **Live Dashboard** | 1 | 3 | Ready |
| **Notifications** | 0 | 4 | Ready |
| **Content Control** | 4 | 3 | Ready |
| **Agenda** | 0 | 1 | Ready |

---

## Recommended Implementation Order

1. **Chat** - Most foundational, teaches the patterns
2. **Reactions** - Enhances chat, simple to add
3. **Polls** - High engagement feature
4. **Q&A** - Essential for conferences
5. **Gamification UI** - Shows points/achievements
6. **DMs** - Networking feature
7. **Notifications** - Polish feature
8. **Content Control** - Presenter tools

---

*Document generated: December 2024*
*Backend: NestJS + Socket.io + Prisma + Redis*
*Questions? Check the backend code in `real-time-service/src/`*
