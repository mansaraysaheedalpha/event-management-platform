# Polls System - Frontend Integration Guide

> **Document Version:** 2.0
> **Last Updated:** December 2025
> **Backend Service:** real-time-service (NestJS + Socket.io)
> **Namespace:** `/events`

---

## Table of Contents

1. [Overview](#1-overview)
2. [Prerequisites](#2-prerequisites)
3. [TypeScript Interfaces](#3-typescript-interfaces)
4. [Socket Events Reference](#4-socket-events-reference)
5. [Session Join & Poll History](#5-session-join--poll-history)
6. [Polls Open/Close Control](#6-polls-openclose-control)
7. [Creating a Poll (Organizer)](#7-creating-a-poll-organizer)
8. [Submitting a Vote (Attendee)](#8-submitting-a-vote-attendee)
9. [Closing a Poll (Organizer)](#9-closing-a-poll-organizer)
10. [Running a Giveaway (Organizer)](#10-running-a-giveaway-organizer)
11. [Listening for Poll Events](#11-listening-for-poll-events)
12. [State Management](#12-state-management)
13. [UI Component Examples](#13-ui-component-examples)
14. [Error Handling](#14-error-handling)
15. [Permissions Reference](#15-permissions-reference)
16. [GraphQL Operations](#16-graphql-operations)
17. [Complete Integration Example](#17-complete-integration-example)

---

## 1. Overview

The Polls system allows organizers to create interactive polls during sessions. Attendees can vote on options and see live results. The system also supports giveaways where a random winner is selected from voters.

### Key Features
- **Poll History on Join**: Receive all existing polls when joining a session
- **Polls Open/Close Control**: Organizers can enable/disable polls per session
- **Organizer Bypass**: Organizers can create polls even when polls are "closed"
- Real-time poll creation and broadcasting
- Live vote submission with instant result updates
- One vote per user per poll (enforced by backend)
- Poll closing with final results broadcast
- **Giveaway requires closed poll**: Must close poll before running giveaway
- Idempotency keys to prevent duplicate submissions
- Gamification points awarded for voting

---

## 2. Prerequisites

### Socket Connection

Ensure you have an authenticated socket connection to the `/events` namespace:

```typescript
import { io, Socket } from 'socket.io-client';
import { v4 as uuidv4 } from 'uuid';

const socket: Socket = io('http://localhost:3002/events', {
  auth: {
    token: `Bearer ${accessToken}`
  },
  query: {
    sessionId: '<SESSION_ID>',  // Required for polls
    eventId: '<EVENT_ID>'
  },
  transports: ['websocket']
});
```

### Required Permissions

| Action | Required Permission |
|--------|---------------------|
| Create Poll | `poll:create` |
| Submit Vote | None (any authenticated user) |
| Close Poll | `poll:manage` |
| Start Giveaway | `poll:manage` |

---

## 3. TypeScript Interfaces

```typescript
// ============================================
// REQUEST DTOs (What you SEND to the backend)
// ============================================

interface PollOptionInput {
  text: string;  // Max 200 characters
}

interface CreatePollRequest {
  question: string;           // Max 500 characters
  options: PollOptionInput[]; // Minimum 2 options required
  idempotencyKey: string;     // UUIDv4 - prevents duplicate polls
}

interface SubmitVoteRequest {
  pollId: string;         // UUIDv4
  optionId: string;       // UUIDv4
  idempotencyKey: string; // UUIDv4 - prevents duplicate votes
}

interface ManagePollRequest {
  pollId: string;         // UUIDv4
  action: 'close';        // Currently only 'close' is supported
  idempotencyKey: string; // UUIDv4
}

interface StartGiveawayRequest {
  pollId: string;           // UUIDv4
  winningOptionId: string;  // UUIDv4 - the correct answer option
  prize: string;            // Max 255 characters
  idempotencyKey: string;   // UUIDv4
}

// ============================================
// RESPONSE TYPES (What you RECEIVE from backend)
// ============================================

interface PollCreator {
  id: string;
  firstName: string | null;
  lastName: string | null;
}

interface PollOption {
  id: string;
  text: string;
  pollId: string;
  voteCount?: number;  // Present in results
}

interface Poll {
  id: string;
  question: string;
  isActive: boolean;
  createdAt: string;      // ISO date string
  expiresAt: string | null;
  creatorId: string;
  sessionId: string;
  options: PollOption[];
  totalVotes?: number;    // Present in results
  creator?: PollCreator;
}

// Wrapper returned by vote submission and poll close events
interface PollResultEnvelope {
  poll: Poll;
  userVotedForOptionId: string | null;  // The option ID the current user voted for
}

interface GiveawayResult {
  pollId: string;
  winner: {
    id: string;
    firstName: string | null;
    lastName: string | null;
  } | null;
  prize: string;
}

// Standard response from emit callbacks
interface SocketResponse<T = void> {
  success: boolean;
  pollId?: string;
  error?: string;
  finalStatus?: string;
  winner?: T;
}
```

---

## 4. Socket Events Reference

### Events You EMIT (Client -> Server)

| Event Name | Payload | Response | Description |
|------------|---------|----------|-------------|
| `poll.create` | `CreatePollRequest` | `{ success, pollId, error }` | Create a new poll |
| `poll.vote.submit` | `SubmitVoteRequest` | `{ success, pollId, error }` | Submit a vote |
| `poll.manage` | `ManagePollRequest` | `{ success, pollId, finalStatus, error }` | Close a poll |
| `poll.giveaway.start` | `StartGiveawayRequest` | `{ success, winner, error }` | Start a giveaway |

### Events You LISTEN TO (Server -> Client)

| Event Name | Payload | When Triggered |
|------------|---------|----------------|
| `poll.history` | `{ polls: PollResultEnvelope[] }` | Sent after `session.join` - all existing polls |
| `poll.opened` | `Poll` | A new poll was created in the session |
| `poll.results.updated` | `PollResultEnvelope` | Someone voted (live results update) |
| `poll.closed` | `PollResultEnvelope` | Poll was closed by organizer |
| `poll.giveaway.winner` | `GiveawayResult` | Giveaway winner was selected |
| `polls.status.changed` | `{ sessionId, isOpen, message }` | Organizer toggled polls open/closed |

---

## 5. Session Join & Poll History

When a user joins a session, they automatically receive:
1. **Session status** in the `session.join` callback (includes `pollsEnabled` and `pollsOpen`)
2. **Poll history** via the `poll.history` event (all existing polls with user's votes)

### Session Join Response

```typescript
interface SessionJoinResponse {
  success: boolean;
  session?: {
    chatEnabled: boolean;
    qaEnabled: boolean;
    pollsEnabled: boolean;  // Is polls feature enabled for this session?
    chatOpen: boolean;
    qaOpen: boolean;
    pollsOpen: boolean;     // Are polls currently open for attendees?
  };
  error?: { message: string; statusCode: number };
}

// Join a session and get status
socket.emit('session.join', { sessionId, eventId }, (response: SessionJoinResponse) => {
  if (response.success && response.session) {
    // Store session feature states
    setPollsEnabled(response.session.pollsEnabled);
    setPollsOpen(response.session.pollsOpen);
  }
});
```

### Poll History Event

```typescript
interface PollHistoryPayload {
  polls: PollResultEnvelope[];  // All polls with results and user's vote status
}

// Listen for poll history after joining
socket.on('poll.history', (payload: PollHistoryPayload) => {
  // Initialize your polls state with existing polls
  payload.polls.forEach(({ poll, userVotedForOptionId }) => {
    addPollToState(poll);
    if (userVotedForOptionId) {
      markUserVote(poll.id, userVotedForOptionId);
    }
  });
});
```

---

## 6. Polls Open/Close Control

Organizers can toggle polls open/closed at the session level using GraphQL. When polls are **closed**:
- **Attendees**: Cannot create polls or vote (blocked)
- **Organizers/Speakers**: Can still create polls (bypass)

### Listening for Status Changes

```typescript
interface PollsStatusPayload {
  sessionId: string;
  isOpen: boolean;
  message: string;  // Human-readable message
}

socket.on('polls.status.changed', (payload: PollsStatusPayload) => {
  console.log(payload.message);
  // Update your local state
  setPollsOpen(payload.isOpen);

  // Optionally show a toast notification
  if (payload.isOpen) {
    toast.success('Polls are now open!');
  } else {
    toast.info('Polls are now closed.');
  }
});
```

### UI Behavior Based on Status

```typescript
// Check if user can interact with polls
function canUserInteract(pollsEnabled: boolean, pollsOpen: boolean, isOrganizer: boolean): boolean {
  if (!pollsEnabled) return false;  // Feature completely disabled
  if (pollsOpen) return true;       // Open for everyone
  return isOrganizer;               // Closed but organizers can bypass
}

// Example component logic
const canVote = pollsOpen;  // Only when open
const canCreatePoll = pollsEnabled && (pollsOpen || hasPermission('poll:create'));
```

---

## 7. Creating a Poll (Organizer)

### Basic Usage

```typescript
import { v4 as uuidv4 } from 'uuid';

async function createPoll(question: string, options: string[]): Promise<string | null> {
  return new Promise((resolve) => {
    const payload: CreatePollRequest = {
      question,
      options: options.map(text => ({ text })),
      idempotencyKey: uuidv4()
    };

    socket.emit('poll.create', payload, (response: SocketResponse) => {
      if (response.success) {
        console.log('Poll created:', response.pollId);
        resolve(response.pollId!);
      } else {
        console.error('Failed to create poll:', response.error);
        resolve(null);
      }
    });
  });
}

// Example usage
await createPoll('What topic should we cover next?', [
  'Advanced TypeScript',
  'React Performance',
  'GraphQL Deep Dive',
  'Testing Strategies'
]);
```

### React Hook Example

```typescript
import { useState, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';

interface UseCreatePollReturn {
  createPoll: (question: string, options: string[]) => Promise<boolean>;
  isCreating: boolean;
  error: string | null;
}

export function useCreatePoll(socket: Socket): UseCreatePollReturn {
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const createPoll = useCallback(async (question: string, options: string[]): Promise<boolean> => {
    if (options.length < 2) {
      setError('At least 2 options are required');
      return false;
    }

    setIsCreating(true);
    setError(null);

    return new Promise((resolve) => {
      socket.emit('poll.create', {
        question,
        options: options.map(text => ({ text })),
        idempotencyKey: uuidv4()
      }, (response: SocketResponse) => {
        setIsCreating(false);
        if (response.success) {
          resolve(true);
        } else {
          setError(response.error || 'Failed to create poll');
          resolve(false);
        }
      });
    });
  }, [socket]);

  return { createPoll, isCreating, error };
}
```

---

## 6. Submitting a Vote (Attendee)

### Basic Usage

```typescript
async function submitVote(pollId: string, optionId: string): Promise<boolean> {
  return new Promise((resolve) => {
    const payload: SubmitVoteRequest = {
      pollId,
      optionId,
      idempotencyKey: uuidv4()
    };

    socket.emit('poll.vote.submit', payload, (response: SocketResponse) => {
      if (response.success) {
        console.log('Vote submitted successfully');
        resolve(true);
      } else {
        console.error('Failed to submit vote:', response.error);
        resolve(false);
      }
    });
  });
}
```

### React Hook Example

```typescript
import { useState, useCallback } from 'react';
import { v4 as uuidv4 } from 'uuid';

interface UseVoteReturn {
  submitVote: (pollId: string, optionId: string) => Promise<boolean>;
  isVoting: boolean;
  error: string | null;
}

export function useVote(socket: Socket): UseVoteReturn {
  const [isVoting, setIsVoting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submitVote = useCallback(async (pollId: string, optionId: string): Promise<boolean> => {
    setIsVoting(true);
    setError(null);

    return new Promise((resolve) => {
      socket.emit('poll.vote.submit', {
        pollId,
        optionId,
        idempotencyKey: uuidv4()
      }, (response: SocketResponse) => {
        setIsVoting(false);
        if (response.success) {
          resolve(true);
        } else {
          setError(response.error || 'Failed to submit vote');
          resolve(false);
        }
      });
    });
  }, [socket]);

  return { submitVote, isVoting, error };
}
```

---

## 7. Closing a Poll (Organizer)

### Basic Usage

```typescript
async function closePoll(pollId: string): Promise<boolean> {
  return new Promise((resolve) => {
    const payload: ManagePollRequest = {
      pollId,
      action: 'close',
      idempotencyKey: uuidv4()
    };

    socket.emit('poll.manage', payload, (response: SocketResponse) => {
      if (response.success) {
        console.log('Poll closed. Final status:', response.finalStatus);
        resolve(true);
      } else {
        console.error('Failed to close poll:', response.error);
        resolve(false);
      }
    });
  });
}
```

---

## 8. Running a Giveaway (Organizer)

After closing a poll, organizers can run a giveaway to select a random winner from users who voted for the correct/winning option.

### Basic Usage

```typescript
async function startGiveaway(
  pollId: string,
  winningOptionId: string,
  prize: string
): Promise<GiveawayResult['winner']> {
  return new Promise((resolve) => {
    const payload: StartGiveawayRequest = {
      pollId,
      winningOptionId,
      prize,
      idempotencyKey: uuidv4()
    };

    socket.emit('poll.giveaway.start', payload, (response: SocketResponse<GiveawayResult['winner']>) => {
      if (response.success) {
        console.log('Giveaway winner:', response.winner);
        resolve(response.winner || null);
      } else {
        console.error('Failed to start giveaway:', response.error);
        resolve(null);
      }
    });
  });
}

// Example: Run giveaway for users who voted for option "opt_abc123"
const winner = await startGiveaway(
  'poll_xyz789',
  'opt_abc123',  // The correct answer option ID
  'Amazon Gift Card $50'
);
```

---

## 9. Listening for Poll Events

### Setting Up Event Listeners

```typescript
// Listen for new polls
socket.on('poll.opened', (poll: Poll) => {
  console.log('New poll:', poll.question);
  // Add to your polls state
  addPollToState(poll);
});

// Listen for vote updates (real-time results)
socket.on('poll.results.updated', (envelope: PollResultEnvelope) => {
  console.log('Results updated for poll:', envelope.poll.id);
  console.log('Total votes:', envelope.poll.totalVotes);
  // Update your polls state with new results
  updatePollInState(envelope.poll);

  // Optionally track user's vote
  if (envelope.userVotedForOptionId) {
    markUserVote(envelope.poll.id, envelope.userVotedForOptionId);
  }
});

// Listen for poll closure
socket.on('poll.closed', (envelope: PollResultEnvelope) => {
  console.log('Poll closed:', envelope.poll.id);
  // Mark poll as inactive and show final results
  updatePollInState({ ...envelope.poll, isActive: false });
});

// Listen for giveaway winners
socket.on('poll.giveaway.winner', (result: GiveawayResult) => {
  console.log('Giveaway winner:', result.winner);
  // Show winner announcement modal/toast
  showGiveawayWinner(result);
});
```

### React Hook for Poll Events

```typescript
import { useEffect, useState, useCallback } from 'react';

interface PollState {
  polls: Map<string, Poll>;
  userVotes: Map<string, string>;  // pollId -> optionId
}

export function usePollEvents(socket: Socket) {
  const [state, setState] = useState<PollState>({
    polls: new Map(),
    userVotes: new Map()
  });
  const [latestGiveaway, setLatestGiveaway] = useState<GiveawayResult | null>(null);

  useEffect(() => {
    // New poll created
    const handlePollOpened = (poll: Poll) => {
      setState(prev => {
        const newPolls = new Map(prev.polls);
        newPolls.set(poll.id, poll);
        return { ...prev, polls: newPolls };
      });
    };

    // Results updated
    const handleResultsUpdated = (envelope: PollResultEnvelope) => {
      setState(prev => {
        const newPolls = new Map(prev.polls);
        newPolls.set(envelope.poll.id, envelope.poll);

        const newVotes = new Map(prev.userVotes);
        if (envelope.userVotedForOptionId) {
          newVotes.set(envelope.poll.id, envelope.userVotedForOptionId);
        }

        return { polls: newPolls, userVotes: newVotes };
      });
    };

    // Poll closed
    const handlePollClosed = (envelope: PollResultEnvelope) => {
      setState(prev => {
        const newPolls = new Map(prev.polls);
        newPolls.set(envelope.poll.id, { ...envelope.poll, isActive: false });
        return { ...prev, polls: newPolls };
      });
    };

    // Giveaway winner
    const handleGiveawayWinner = (result: GiveawayResult) => {
      setLatestGiveaway(result);
    };

    socket.on('poll.opened', handlePollOpened);
    socket.on('poll.results.updated', handleResultsUpdated);
    socket.on('poll.closed', handlePollClosed);
    socket.on('poll.giveaway.winner', handleGiveawayWinner);

    return () => {
      socket.off('poll.opened', handlePollOpened);
      socket.off('poll.results.updated', handleResultsUpdated);
      socket.off('poll.closed', handlePollClosed);
      socket.off('poll.giveaway.winner', handleGiveawayWinner);
    };
  }, [socket]);

  // Helper to get active polls
  const activePolls = Array.from(state.polls.values()).filter(p => p.isActive);
  const closedPolls = Array.from(state.polls.values()).filter(p => !p.isActive);

  // Check if user has voted on a poll
  const hasVoted = useCallback((pollId: string) => state.userVotes.has(pollId), [state.userVotes]);
  const getUserVote = useCallback((pollId: string) => state.userVotes.get(pollId), [state.userVotes]);

  return {
    polls: state.polls,
    activePolls,
    closedPolls,
    hasVoted,
    getUserVote,
    latestGiveaway,
    clearGiveaway: () => setLatestGiveaway(null)
  };
}
```

---

## 10. State Management

### Recommended State Structure

```typescript
interface PollsState {
  // All polls indexed by ID
  pollsById: Record<string, Poll>;

  // User's votes: pollId -> optionId
  userVotes: Record<string, string>;

  // Loading states
  isCreatingPoll: boolean;
  isVoting: Record<string, boolean>;  // pollId -> isVoting
  isClosingPoll: Record<string, boolean>;

  // Error states
  createError: string | null;
  voteErrors: Record<string, string>;  // pollId -> error

  // Active poll ID (if showing one at a time)
  activePollId: string | null;
}
```

### Zustand Store Example

```typescript
import { create } from 'zustand';

interface PollsStore {
  polls: Map<string, Poll>;
  userVotes: Map<string, string>;

  // Actions
  addPoll: (poll: Poll) => void;
  updatePoll: (poll: Poll) => void;
  setUserVote: (pollId: string, optionId: string) => void;
  hasVoted: (pollId: string) => boolean;
}

export const usePollsStore = create<PollsStore>((set, get) => ({
  polls: new Map(),
  userVotes: new Map(),

  addPoll: (poll) => set((state) => {
    const newPolls = new Map(state.polls);
    newPolls.set(poll.id, poll);
    return { polls: newPolls };
  }),

  updatePoll: (poll) => set((state) => {
    const newPolls = new Map(state.polls);
    newPolls.set(poll.id, poll);
    return { polls: newPolls };
  }),

  setUserVote: (pollId, optionId) => set((state) => {
    const newVotes = new Map(state.userVotes);
    newVotes.set(pollId, optionId);
    return { userVotes: newVotes };
  }),

  hasVoted: (pollId) => get().userVotes.has(pollId)
}));
```

---

## 11. UI Component Examples

### Poll Card Component

```tsx
import React from 'react';

interface PollCardProps {
  poll: Poll;
  userVotedOptionId: string | null;
  onVote: (optionId: string) => void;
  onClose?: () => void;  // Only for organizers
  isVoting: boolean;
  canManage: boolean;
}

export function PollCard({
  poll,
  userVotedOptionId,
  onVote,
  onClose,
  isVoting,
  canManage
}: PollCardProps) {
  const hasVoted = userVotedOptionId !== null;
  const showResults = hasVoted || !poll.isActive;

  return (
    <div className="poll-card">
      <div className="poll-header">
        <h3>{poll.question}</h3>
        {!poll.isActive && <span className="badge">Closed</span>}
      </div>

      <div className="poll-options">
        {poll.options.map((option) => {
          const isSelected = option.id === userVotedOptionId;
          const percentage = poll.totalVotes
            ? Math.round((option.voteCount! / poll.totalVotes) * 100)
            : 0;

          return (
            <button
              key={option.id}
              className={`poll-option ${isSelected ? 'selected' : ''}`}
              onClick={() => onVote(option.id)}
              disabled={hasVoted || !poll.isActive || isVoting}
            >
              <span className="option-text">{option.text}</span>

              {showResults && (
                <>
                  <div
                    className="progress-bar"
                    style={{ width: `${percentage}%` }}
                  />
                  <span className="vote-count">
                    {option.voteCount} votes ({percentage}%)
                  </span>
                </>
              )}

              {isSelected && <span className="check-mark">✓</span>}
            </button>
          );
        })}
      </div>

      <div className="poll-footer">
        <span>{poll.totalVotes || 0} total votes</span>

        {canManage && poll.isActive && (
          <button onClick={onClose} className="close-poll-btn">
            Close Poll
          </button>
        )}
      </div>
    </div>
  );
}
```

### Create Poll Form

```tsx
import React, { useState } from 'react';

interface CreatePollFormProps {
  onSubmit: (question: string, options: string[]) => Promise<boolean>;
  isSubmitting: boolean;
}

export function CreatePollForm({ onSubmit, isSubmitting }: CreatePollFormProps) {
  const [question, setQuestion] = useState('');
  const [options, setOptions] = useState(['', '']);

  const addOption = () => {
    if (options.length < 10) {
      setOptions([...options, '']);
    }
  };

  const removeOption = (index: number) => {
    if (options.length > 2) {
      setOptions(options.filter((_, i) => i !== index));
    }
  };

  const updateOption = (index: number, value: string) => {
    const newOptions = [...options];
    newOptions[index] = value;
    setOptions(newOptions);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    const validOptions = options.filter(o => o.trim());
    if (validOptions.length < 2) {
      alert('Please provide at least 2 options');
      return;
    }

    const success = await onSubmit(question, validOptions);
    if (success) {
      setQuestion('');
      setOptions(['', '']);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="create-poll-form">
      <div className="form-group">
        <label>Question</label>
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question..."
          maxLength={500}
          required
        />
      </div>

      <div className="form-group">
        <label>Options</label>
        {options.map((option, index) => (
          <div key={index} className="option-input">
            <input
              type="text"
              value={option}
              onChange={(e) => updateOption(index, e.target.value)}
              placeholder={`Option ${index + 1}`}
              maxLength={200}
            />
            {options.length > 2 && (
              <button type="button" onClick={() => removeOption(index)}>
                Remove
              </button>
            )}
          </div>
        ))}

        {options.length < 10 && (
          <button type="button" onClick={addOption}>
            + Add Option
          </button>
        )}
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Creating...' : 'Create Poll'}
      </button>
    </form>
  );
}
```

### Giveaway Winner Modal

```tsx
import React from 'react';

interface GiveawayModalProps {
  result: GiveawayResult;
  onClose: () => void;
}

export function GiveawayModal({ result, onClose }: GiveawayModalProps) {
  if (!result.winner) {
    return (
      <div className="modal giveaway-modal">
        <h2>No Winner</h2>
        <p>No one voted for the winning option.</p>
        <button onClick={onClose}>Close</button>
      </div>
    );
  }

  const winnerName = [result.winner.firstName, result.winner.lastName]
    .filter(Boolean)
    .join(' ') || 'Anonymous';

  return (
    <div className="modal giveaway-modal">
      <div className="confetti-animation" />
      <h2>Congratulations!</h2>
      <div className="winner-info">
        <span className="winner-name">{winnerName}</span>
        <span className="winner-label">wins</span>
        <span className="prize">{result.prize}</span>
      </div>
      <button onClick={onClose}>Close</button>
    </div>
  );
}
```

---

## 12. Error Handling

### Common Errors

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `"Duplicate request..."` | Same idempotency key used twice | Generate new UUID for each request |
| `"You do not have permission to create a poll"` | Missing `poll:create` permission | Check user permissions |
| `"You do not have permission to manage polls"` | Missing `poll:manage` permission | Check user permissions |
| `"Poll with ID X not found"` | Invalid poll ID | Verify poll exists |
| `"This poll is no longer active"` | Voting on closed poll | Disable vote buttons for closed polls |
| `"You have already voted in this poll"` | User trying to vote twice | Track user's votes locally |

### Error Handling Pattern

```typescript
socket.emit('poll.vote.submit', payload, (response: SocketResponse) => {
  if (!response.success) {
    switch (true) {
      case response.error?.includes('already voted'):
        // User already voted - update local state
        toast.info('You have already voted in this poll');
        break;
      case response.error?.includes('no longer active'):
        // Poll was closed - refresh poll state
        toast.warning('This poll has been closed');
        break;
      case response.error?.includes('Duplicate'):
        // Idempotency conflict - likely a retry, ignore
        break;
      default:
        toast.error(response.error || 'Failed to submit vote');
    }
  }
});
```

---

## 13. Permissions Reference

### Required Permissions by Action

```typescript
const POLL_PERMISSIONS = {
  CREATE: 'poll:create',
  MANAGE: 'poll:manage',  // Close poll, start giveaway
  VOTE: null  // Any authenticated user can vote
} as const;

// Check if user can create polls
function canCreatePoll(permissions: string[]): boolean {
  return permissions.includes(POLL_PERMISSIONS.CREATE);
}

// Check if user can manage polls
function canManagePoll(permissions: string[]): boolean {
  return permissions.includes(POLL_PERMISSIONS.MANAGE);
}
```

### Typical Role Mappings

| Role | poll:create | poll:manage | Can Vote |
|------|-------------|-------------|----------|
| Admin | Yes | Yes | Yes |
| Organizer | Yes | Yes | Yes |
| Speaker | Yes | No | Yes |
| Moderator | No | No | Yes |
| Attendee | No | No | Yes |

---

## 14. Complete Integration Example

### Full React Component

```tsx
import React, { useEffect, useState } from 'react';
import { Socket } from 'socket.io-client';
import { v4 as uuidv4 } from 'uuid';

// Types (from section 3)
interface Poll { /* ... */ }
interface PollResultEnvelope { /* ... */ }
interface GiveawayResult { /* ... */ }

interface PollsContainerProps {
  socket: Socket;
  userPermissions: string[];
}

export function PollsContainer({ socket, userPermissions }: PollsContainerProps) {
  const [polls, setPolls] = useState<Map<string, Poll>>(new Map());
  const [userVotes, setUserVotes] = useState<Map<string, string>>(new Map());
  const [giveawayResult, setGiveawayResult] = useState<GiveawayResult | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [votingPollId, setVotingPollId] = useState<string | null>(null);

  const canCreate = userPermissions.includes('poll:create');
  const canManage = userPermissions.includes('poll:manage');

  // Set up event listeners
  useEffect(() => {
    const handlePollOpened = (poll: Poll) => {
      setPolls(prev => new Map(prev).set(poll.id, poll));
    };

    const handleResultsUpdated = (envelope: PollResultEnvelope) => {
      setPolls(prev => new Map(prev).set(envelope.poll.id, envelope.poll));
      if (envelope.userVotedForOptionId) {
        setUserVotes(prev => new Map(prev).set(envelope.poll.id, envelope.userVotedForOptionId));
      }
    };

    const handlePollClosed = (envelope: PollResultEnvelope) => {
      setPolls(prev => new Map(prev).set(envelope.poll.id, { ...envelope.poll, isActive: false }));
    };

    const handleGiveawayWinner = (result: GiveawayResult) => {
      setGiveawayResult(result);
    };

    socket.on('poll.opened', handlePollOpened);
    socket.on('poll.results.updated', handleResultsUpdated);
    socket.on('poll.closed', handlePollClosed);
    socket.on('poll.giveaway.winner', handleGiveawayWinner);

    return () => {
      socket.off('poll.opened', handlePollOpened);
      socket.off('poll.results.updated', handleResultsUpdated);
      socket.off('poll.closed', handlePollClosed);
      socket.off('poll.giveaway.winner', handleGiveawayWinner);
    };
  }, [socket]);

  // Create poll handler
  const handleCreatePoll = async (question: string, options: string[]) => {
    setIsCreating(true);

    socket.emit('poll.create', {
      question,
      options: options.map(text => ({ text })),
      idempotencyKey: uuidv4()
    }, (response: { success: boolean; error?: string }) => {
      setIsCreating(false);
      if (!response.success) {
        console.error('Failed to create poll:', response.error);
      }
    });
  };

  // Vote handler
  const handleVote = async (pollId: string, optionId: string) => {
    setVotingPollId(pollId);

    socket.emit('poll.vote.submit', {
      pollId,
      optionId,
      idempotencyKey: uuidv4()
    }, (response: { success: boolean; error?: string }) => {
      setVotingPollId(null);
      if (!response.success) {
        console.error('Failed to vote:', response.error);
      }
    });
  };

  // Close poll handler
  const handleClosePoll = async (pollId: string) => {
    socket.emit('poll.manage', {
      pollId,
      action: 'close',
      idempotencyKey: uuidv4()
    });
  };

  // Get active and closed polls
  const activePolls = Array.from(polls.values()).filter(p => p.isActive);
  const closedPolls = Array.from(polls.values()).filter(p => !p.isActive);

  return (
    <div className="polls-container">
      {/* Create Poll Form (for organizers) */}
      {canCreate && (
        <CreatePollForm
          onSubmit={handleCreatePoll}
          isSubmitting={isCreating}
        />
      )}

      {/* Active Polls */}
      <section>
        <h2>Active Polls</h2>
        {activePolls.length === 0 ? (
          <p>No active polls</p>
        ) : (
          activePolls.map(poll => (
            <PollCard
              key={poll.id}
              poll={poll}
              userVotedOptionId={userVotes.get(poll.id) || null}
              onVote={(optionId) => handleVote(poll.id, optionId)}
              onClose={() => handleClosePoll(poll.id)}
              isVoting={votingPollId === poll.id}
              canManage={canManage}
            />
          ))
        )}
      </section>

      {/* Closed Polls */}
      {closedPolls.length > 0 && (
        <section>
          <h2>Closed Polls</h2>
          {closedPolls.map(poll => (
            <PollCard
              key={poll.id}
              poll={poll}
              userVotedOptionId={userVotes.get(poll.id) || null}
              onVote={() => {}}
              isVoting={false}
              canManage={false}
            />
          ))}
        </section>
      )}

      {/* Giveaway Winner Modal */}
      {giveawayResult && (
        <GiveawayModal
          result={giveawayResult}
          onClose={() => setGiveawayResult(null)}
        />
      )}
    </div>
  );
}
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    POLLS QUICK REFERENCE                     │
├─────────────────────────────────────────────────────────────┤
│ EMIT EVENTS (Client → Server)                               │
│ ─────────────────────────────────────────────────────────── │
│ poll.create         → Creates new poll                      │
│ poll.vote.submit    → Submits a vote                        │
│ poll.manage         → Closes a poll                         │
│ poll.giveaway.start → Selects random winner                 │
├─────────────────────────────────────────────────────────────┤
│ LISTEN EVENTS (Server → Client)                             │
│ ─────────────────────────────────────────────────────────── │
│ poll.opened          ← New poll created                     │
│ poll.results.updated ← Vote submitted (live results)        │
│ poll.closed          ← Poll closed by organizer             │
│ poll.giveaway.winner ← Winner selected                      │
├─────────────────────────────────────────────────────────────┤
│ PERMISSIONS                                                 │
│ ─────────────────────────────────────────────────────────── │
│ poll:create  → Create polls                                 │
│ poll:manage  → Close polls, run giveaways                   │
│ (none)       → Vote (any authenticated user)                │
├─────────────────────────────────────────────────────────────┤
│ IDEMPOTENCY                                                 │
│ ─────────────────────────────────────────────────────────── │
│ Always include a unique UUIDv4 idempotencyKey in requests   │
│ This prevents duplicate submissions on retries/reconnects   │
└─────────────────────────────────────────────────────────────┘
```

---

## 16. GraphQL Operations

### Session Type (Query)

The Session type now includes polls fields:

```graphql
type Session {
  id: ID!
  title: String!
  startTime: DateTime!
  endTime: DateTime!
  chatEnabled: Boolean!
  qaEnabled: Boolean!
  pollsEnabled: Boolean!   # Is polls feature enabled?
  chatOpen: Boolean!
  qaOpen: Boolean!
  pollsOpen: Boolean!      # Are polls currently open?
  speakers: [Speaker!]!
}
```

### Toggle Polls Mutation

Organizers can open/close polls using the `toggleSessionPolls` mutation:

```graphql
mutation ToggleSessionPolls($id: String!, $open: Boolean!) {
  toggleSessionPolls(id: $id, open: $open) {
    id
    pollsOpen
    pollsEnabled
  }
}
```

### React Hook for Toggle

```typescript
import { useMutation, gql } from '@apollo/client';

const TOGGLE_SESSION_POLLS = gql`
  mutation ToggleSessionPolls($id: String!, $open: Boolean!) {
    toggleSessionPolls(id: $id, open: $open) {
      id
      pollsOpen
    }
  }
`;

export function useTogglePolls() {
  const [togglePolls, { loading, error }] = useMutation(TOGGLE_SESSION_POLLS);

  const openPolls = (sessionId: string) => togglePolls({
    variables: { id: sessionId, open: true }
  });

  const closePolls = (sessionId: string) => togglePolls({
    variables: { id: sessionId, open: false }
  });

  return { openPolls, closePolls, loading, error };
}
```

### Create/Update Session with Polls Settings

```graphql
input SessionCreateInput {
  eventId: String!
  title: String!
  sessionDate: String!
  startTime: String!
  endTime: String!
  speakerIds: [String!]
  chatEnabled: Boolean = true
  qaEnabled: Boolean = true
  pollsEnabled: Boolean = true  # Enable/disable polls for this session
}

input SessionUpdateInput {
  title: String
  startTime: String
  endTime: String
  speakerIds: [String!]
  chatEnabled: Boolean
  qaEnabled: Boolean
  pollsEnabled: Boolean  # Enable/disable polls feature
}
```

---

## 17. Quick Reference Card

```
┌─────────────────────────────────────────────────────────────┐
│                    POLLS QUICK REFERENCE                     │
├─────────────────────────────────────────────────────────────┤
│ EMIT EVENTS (Client → Server)                               │
│ ─────────────────────────────────────────────────────────── │
│ poll.create         → Creates new poll                      │
│ poll.vote.submit    → Submits a vote                        │
│ poll.manage         → Closes a poll                         │
│ poll.giveaway.start → Selects random winner                 │
├─────────────────────────────────────────────────────────────┤
│ LISTEN EVENTS (Server → Client)                             │
│ ─────────────────────────────────────────────────────────── │
│ poll.history         ← All polls on session join            │
│ poll.opened          ← New poll created                     │
│ poll.results.updated ← Vote submitted (live results)        │
│ poll.closed          ← Poll closed by organizer             │
│ poll.giveaway.winner ← Winner selected                      │
│ polls.status.changed ← Polls open/closed toggled            │
├─────────────────────────────────────────────────────────────┤
│ GRAPHQL MUTATIONS                                           │
│ ─────────────────────────────────────────────────────────── │
│ toggleSessionPolls   → Open/close polls for session         │
├─────────────────────────────────────────────────────────────┤
│ PERMISSIONS                                                 │
│ ─────────────────────────────────────────────────────────── │
│ poll:create  → Create polls                                 │
│ poll:manage  → Close polls, run giveaways                   │
│ (none)       → Vote (any authenticated user)                │
├─────────────────────────────────────────────────────────────┤
│ IMPORTANT RULES                                             │
│ ─────────────────────────────────────────────────────────── │
│ • Giveaway requires closed poll (close poll first!)         │
│ • Organizers bypass pollsOpen check (can always create)     │
│ • Always use unique idempotencyKey per request              │
└─────────────────────────────────────────────────────────────┘
```

---

## Need Help?

- **Chat Feature Guide**: See `REALTIME_SERVICE_FRONTEND_GUIDE.md`
- **Backend Source**: `real-time-service/src/comm/polls/`
- **API Gateway**: GraphQL operations available via Apollo Gateway
