// Ported from ../globalconnect/src/hooks/use-session-qa.ts
// Mobile-adapted: no IndexedDB, always uses shared socket from SessionSocketProvider

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useSessionSocket } from '@/context/SessionSocketContext';
import { useAuthStore } from '@/store/auth.store';

const generateUUID = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

export interface QuestionAuthor {
  id: string;
  firstName: string;
  lastName: string;
}

export interface QuestionAnswer {
  id: string;
  createdAt: string;
  text: string;
  author: { id: string; firstName: string; lastName: string };
}

export type QuestionStatus = 'pending' | 'approved' | 'dismissed';

export interface Question {
  id: string;
  text: string;
  isAnonymous: boolean;
  status: QuestionStatus;
  createdAt: string;
  updatedAt: string;
  isAnswered: boolean;
  tags: string[];
  authorId: string;
  sessionId: string;
  author: QuestionAuthor;
  _count: { upvotes: number };
  answer?: QuestionAnswer;
  hasUpvoted?: boolean;
}

interface OptimisticQuestion extends Question {
  isOptimistic?: boolean;
  optimisticId?: string;
}

interface QAResponse {
  success: boolean;
  questionId?: string;
  error?: { message: string; statusCode: number } | string;
}

export type QASortMode = 'upvotes' | 'recent';
export type QAFilterMode = 'all' | 'answered' | 'unanswered';

export function useSessionQA() {
  const { socket, isConnected, isJoined, qaOpen, sessionId } = useSessionSocket();
  const { user } = useAuthStore();

  const [questions, setQuestions] = useState<OptimisticQuestion[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sortMode, setSortMode] = useState<QASortMode>('upvotes');
  const [filterMode, setFilterMode] = useState<QAFilterMode>('all');
  const questionsRef = useRef<OptimisticQuestion[]>([]);

  useEffect(() => {
    questionsRef.current = questions;
  }, [questions]);

  // Socket event listeners
  useEffect(() => {
    if (!socket) return;

    const handleHistory = (data: { questions: Question[] }) => {
      if (data?.questions && Array.isArray(data.questions)) {
        setQuestions(data.questions);
      }
    };

    const handleNewQuestion = (question: Question) => {
      setQuestions((prev) => {
        const optimisticIdx = prev.findIndex(
          (q) => (q as OptimisticQuestion).isOptimistic && q.text === question.text && q.authorId === question.authorId,
        );
        if (optimisticIdx !== -1) {
          const updated = [...prev];
          updated[optimisticIdx] = question;
          return updated;
        }
        // Dedup by ID
        if (prev.some((q) => q.id === question.id)) return prev;
        return [...prev, question];
      });
    };

    const handleQuestionUpdated = (updated: Question) => {
      setQuestions((prev) => prev.map((q) => (q.id === updated.id ? { ...q, ...updated } : q)));
    };

    const handleQuestionRemoved = (data: { questionId: string }) => {
      setQuestions((prev) => prev.filter((q) => q.id !== data.questionId));
    };

    socket.on('qa.history', handleHistory);
    socket.on('qa.question.new', handleNewQuestion);
    socket.on('qna.question.updated', handleQuestionUpdated);
    socket.on('qna.question.removed', handleQuestionRemoved);

    return () => {
      socket.off('qa.history', handleHistory);
      socket.off('qa.question.new', handleNewQuestion);
      socket.off('qna.question.updated', handleQuestionUpdated);
      socket.off('qna.question.removed', handleQuestionRemoved);
    };
  }, [socket]);

  const askQuestion = useCallback(
    async (text: string, isAnonymous: boolean = false): Promise<boolean> => {
      const trimmed = text.trim();
      if (!trimmed || trimmed.length > 500 || !socket || !isJoined) return false;

      setIsSending(true);
      const optimisticId = generateUUID();
      const idempotencyKey = generateUUID();
      const now = new Date().toISOString();

      const optimistic: OptimisticQuestion = {
        id: optimisticId,
        text: trimmed,
        isAnonymous,
        status: 'pending',
        createdAt: now,
        updatedAt: now,
        isAnswered: false,
        tags: [],
        authorId: user?.id || '',
        sessionId,
        author: {
          id: user?.id || '',
          firstName: isAnonymous ? 'Anonymous' : (user?.first_name || 'You'),
          lastName: isAnonymous ? '' : (user?.last_name || ''),
        },
        _count: { upvotes: 0 },
        isOptimistic: true,
        optimisticId,
      };

      setQuestions((prev) => [...prev, optimistic]);

      return new Promise((resolve) => {
        const timeoutId = setTimeout(() => {
          setIsSending(false);
          resolve(true);
        }, 5000);

        socket.emit(
          'qa.question.ask',
          { text: trimmed, isAnonymous, idempotencyKey },
          (response: QAResponse) => {
            clearTimeout(timeoutId);
            setIsSending(false);
            if (response?.success) {
              resolve(true);
            } else {
              const errorMsg =
                typeof response?.error === 'string'
                  ? response.error
                  : response?.error?.message || 'Failed to ask question';
              setQuestions((prev) => prev.filter((q) => q.id !== optimisticId));
              setError(errorMsg);
              resolve(false);
            }
          },
        );
      });
    },
    [socket, isJoined, sessionId, user],
  );

  const upvoteQuestion = useCallback(
    async (questionId: string): Promise<boolean> => {
      if (!socket || !isJoined || !user?.id) return false;

      const original = questionsRef.current.find((q) => q.id === questionId);
      if (!original || original.authorId === user.id) return false;

      setQuestions((prev) =>
        prev.map((q) => {
          if (q.id !== questionId) return q;
          const hasUpvoted = q.hasUpvoted || false;
          const currentCount = q._count?.upvotes || 0;
          return {
            ...q,
            hasUpvoted: !hasUpvoted,
            _count: { ...q._count, upvotes: hasUpvoted ? Math.max(0, currentCount - 1) : currentCount + 1 },
          };
        }),
      );

      return new Promise((resolve) => {
        socket.emit(
          'qna.question.upvote',
          { questionId, idempotencyKey: generateUUID() },
          (response: QAResponse) => {
            if (response?.success) {
              resolve(true);
            } else {
              setQuestions((prev) => prev.map((q) => (q.id === questionId ? original : q)));
              resolve(false);
            }
          },
        );
      });
    },
    [socket, isJoined, user?.id],
  );

  const clearError = useCallback(() => setError(null), []);

  // Computed: sorted + filtered
  const sortedFiltered = useMemo(() => {
    let list = [...questions];

    if (filterMode === 'answered') list = list.filter((q) => q.isAnswered);
    else if (filterMode === 'unanswered') list = list.filter((q) => !q.isAnswered);

    if (sortMode === 'upvotes') {
      list.sort((a, b) => (b._count?.upvotes || 0) - (a._count?.upvotes || 0));
    } else {
      list.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
    }
    return list;
  }, [questions, filterMode, sortMode]);

  return {
    questions: sortedFiltered,
    allQuestions: questions,
    isConnected,
    isJoined,
    qaOpen,
    isSending,
    error,
    currentUserId: user?.id,
    sortMode,
    setSortMode,
    filterMode,
    setFilterMode,
    askQuestion,
    upvoteQuestion,
    clearError,
  };
}
