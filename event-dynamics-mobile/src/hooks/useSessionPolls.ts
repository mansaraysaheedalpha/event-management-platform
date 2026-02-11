// Ported from ../globalconnect/src/hooks/use-session-polls.ts
// Mobile-adapted: no IndexedDB, always uses shared socket from SessionSocketProvider

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useSessionSocket } from '@/context/SessionSocketContext';
import { useAuthStore } from '@/store/auth.store';

const generateUUID = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

export interface PollOption {
  id: string;
  text: string;
  pollId: string;
  voteCount?: number;
}

export interface Poll {
  id: string;
  question: string;
  isActive: boolean;
  createdAt: string;
  expiresAt: string | null;
  creatorId: string;
  sessionId: string;
  options: PollOption[];
  totalVotes?: number;
  isQuiz?: boolean;
  correctOptionId?: string;
}

interface PollResultEnvelope {
  poll: Poll;
  userVotedForOptionId: string | null;
}

interface SocketResponse {
  success: boolean;
  pollId?: string;
  error?: { message: string; statusCode: number } | string;
}

export function useSessionPolls() {
  const { socket, isConnected, isJoined, pollsOpen, sessionId } = useSessionSocket();
  const { user } = useAuthStore();

  const [polls, setPolls] = useState<Map<string, Poll>>(new Map());
  const [userVotes, setUserVotes] = useState<Map<string, string>>(new Map());
  const [isVoting, setIsVoting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollsRef = useRef<Map<string, Poll>>(new Map());
  const userVotesRef = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    pollsRef.current = polls;
  }, [polls]);

  useEffect(() => {
    userVotesRef.current = userVotes;
  }, [userVotes]);

  // Socket event listeners
  useEffect(() => {
    if (!socket) return;

    const handlePollHistory = (data: { polls: PollResultEnvelope[] }) => {
      if (data?.polls && Array.isArray(data.polls)) {
        const newPolls = new Map<string, Poll>();
        const newVotes = new Map<string, string>();
        data.polls.forEach(({ poll, userVotedForOptionId }) => {
          newPolls.set(poll.id, poll);
          if (userVotedForOptionId) newVotes.set(poll.id, userVotedForOptionId);
        });
        setPolls(newPolls);
        setUserVotes(newVotes);
      }
    };

    const handlePollOpened = (poll: Poll) => {
      setPolls((prev) => {
        const updated = new Map(prev);
        updated.set(poll.id, poll);
        return updated;
      });
    };

    const handleResultsUpdated = (envelope: PollResultEnvelope) => {
      setPolls((prev) => {
        const updated = new Map(prev);
        updated.set(envelope.poll.id, envelope.poll);
        return updated;
      });
      if (envelope.userVotedForOptionId) {
        setUserVotes((prev) => {
          const updated = new Map(prev);
          updated.set(envelope.poll.id, envelope.userVotedForOptionId!);
          return updated;
        });
      }
    };

    const handlePollClosed = (envelope: PollResultEnvelope) => {
      setPolls((prev) => {
        const updated = new Map(prev);
        updated.set(envelope.poll.id, { ...envelope.poll, isActive: false });
        return updated;
      });
    };

    socket.on('poll.history', handlePollHistory);
    socket.on('poll.opened', handlePollOpened);
    socket.on('poll.results.updated', handleResultsUpdated);
    socket.on('poll.closed', handlePollClosed);

    return () => {
      socket.off('poll.history', handlePollHistory);
      socket.off('poll.opened', handlePollOpened);
      socket.off('poll.results.updated', handleResultsUpdated);
      socket.off('poll.closed', handlePollClosed);
    };
  }, [socket]);

  const submitVote = useCallback(
    async (pollId: string, optionId: string): Promise<boolean> => {
      if (!socket || !isJoined) return false;
      if (userVotesRef.current.has(pollId)) {
        setError('You have already voted in this poll');
        return false;
      }

      const poll = pollsRef.current.get(pollId);
      if (!poll || !poll.isActive) {
        setError('This poll is no longer active');
        return false;
      }

      setIsVoting(pollId);

      // Optimistic update
      setUserVotes((prev) => {
        const updated = new Map(prev);
        updated.set(pollId, optionId);
        return updated;
      });
      setPolls((prev) => {
        const updated = new Map(prev);
        const existing = updated.get(pollId);
        if (existing) {
          updated.set(pollId, {
            ...existing,
            options: existing.options.map((opt) =>
              opt.id === optionId ? { ...opt, voteCount: (opt.voteCount || 0) + 1 } : opt,
            ),
            totalVotes: (existing.totalVotes || 0) + 1,
          });
        }
        return updated;
      });

      return new Promise((resolve) => {
        socket.emit(
          'poll.vote.submit',
          { pollId, optionId, idempotencyKey: generateUUID() },
          (response: SocketResponse) => {
            setIsVoting(null);
            if (response?.success) {
              resolve(true);
            } else {
              // Rollback
              setUserVotes((prev) => {
                const updated = new Map(prev);
                updated.delete(pollId);
                return updated;
              });
              const original = pollsRef.current.get(pollId);
              if (original) {
                setPolls((prev) => {
                  const updated = new Map(prev);
                  updated.set(pollId, original);
                  return updated;
                });
              }
              const errorMsg =
                typeof response?.error === 'string'
                  ? response.error
                  : response?.error?.message || 'Failed to vote';
              setError(errorMsg);
              resolve(false);
            }
          },
        );
      });
    },
    [socket, isJoined],
  );

  const hasVoted = useCallback((pollId: string): boolean => userVotesRef.current.has(pollId), []);
  const getUserVote = useCallback((pollId: string): string | undefined => userVotesRef.current.get(pollId), []);
  const clearError = useCallback(() => setError(null), []);

  // Computed
  const pollsArray = useMemo(() => Array.from(polls.values()), [polls]);
  const activePolls = useMemo(
    () => pollsArray.filter((p) => p.isActive).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
    [pollsArray],
  );
  const closedPolls = useMemo(
    () => pollsArray.filter((p) => !p.isActive).sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
    [pollsArray],
  );

  return {
    polls,
    pollsArray,
    activePolls,
    closedPolls,
    userVotes,
    isConnected,
    isJoined,
    pollsOpen,
    isVoting,
    error,
    currentUserId: user?.id,
    submitVote,
    hasVoted,
    getUserVote,
    clearError,
  };
}
