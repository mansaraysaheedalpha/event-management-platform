// Ported from ../globalconnect/src/hooks/use-session-chat.ts
// Mobile-adapted: no IndexedDB, always uses shared socket from SessionSocketProvider

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSessionSocket } from '@/context/SessionSocketContext';
import { useAuthStore } from '@/store/auth.store';

const generateUUID = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

export interface MessageAuthor {
  id: string;
  firstName: string;
  lastName: string;
}

export interface ParentMessage {
  id: string;
  text: string;
  author: MessageAuthor;
}

export interface ChatMessage {
  id: string;
  text: string;
  timestamp: string;
  isEdited: boolean;
  editedAt: string | null;
  authorId: string;
  sessionId: string;
  author: MessageAuthor;
  parentMessage?: ParentMessage;
  reactionsSummary?: Record<string, number>;
}

interface OptimisticMessage extends ChatMessage {
  isOptimistic?: boolean;
  optimisticId?: string;
}

interface SendMessageResponse {
  success: boolean;
  messageId?: string;
  error?: { message: string; statusCode: number } | string;
}

export function useSessionChat() {
  const { socket, isConnected, isJoined, chatOpen, sessionId } = useSessionSocket();
  const { user } = useAuthStore();

  const [messages, setMessages] = useState<OptimisticMessage[]>([]);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<OptimisticMessage[]>([]);

  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Socket event listeners
  useEffect(() => {
    if (!socket) return;

    const handleChatHistory = (data: { messages: ChatMessage[] }) => {
      if (data?.messages && Array.isArray(data.messages)) {
        setMessages(data.messages);
      }
    };

    const handleNewMessage = (message: ChatMessage) => {
      setMessages((prev) => {
        // Dedup by ID
        const existingById = prev.find((m) => m.id === message.id);
        if (existingById) {
          return prev.map((m) => (m.id === message.id ? message : m));
        }

        // Replace optimistic message
        const optimisticIndex = prev.findIndex(
          (m) => m.optimisticId && m.text === message.text && m.authorId === message.authorId,
        );
        if (optimisticIndex !== -1) {
          const updated = [...prev];
          updated[optimisticIndex] = message;
          return updated;
        }

        // Dedup by timestamp proximity
        const isDuplicate = prev.some(
          (m) =>
            m.text === message.text &&
            m.authorId === message.authorId &&
            Math.abs(new Date(m.timestamp).getTime() - new Date(message.timestamp).getTime()) < 5000,
        );
        if (isDuplicate) return prev;

        return [...prev, message];
      });
    };

    const handleMessageUpdated = (updated: ChatMessage) => {
      setMessages((prev) => prev.map((m) => (m.id === updated.id ? updated : m)));
    };

    const handleMessageDeleted = (data: { messageId: string }) => {
      setMessages((prev) => prev.filter((m) => m.id !== data.messageId));
    };

    socket.on('chat.history', handleChatHistory);
    socket.on('chat.message.new', handleNewMessage);
    socket.on('chat.message.updated', handleMessageUpdated);
    socket.on('chat.message.deleted', handleMessageDeleted);

    return () => {
      socket.off('chat.history', handleChatHistory);
      socket.off('chat.message.new', handleNewMessage);
      socket.off('chat.message.updated', handleMessageUpdated);
      socket.off('chat.message.deleted', handleMessageDeleted);
    };
  }, [socket]);

  const sendMessage = useCallback(
    async (text: string, replyingToMessageId?: string): Promise<boolean> => {
      const trimmedText = text.trim();
      if (!trimmedText || trimmedText.length > 1000 || !socket || !isJoined) return false;

      setIsSending(true);

      const optimisticId = generateUUID();
      const idempotencyKey = generateUUID();

      const parentMsg = replyingToMessageId
        ? messagesRef.current.find((m) => m.id === replyingToMessageId)
        : undefined;

      const optimisticMessage: OptimisticMessage = {
        id: optimisticId,
        text: trimmedText,
        timestamp: new Date().toISOString(),
        isEdited: false,
        editedAt: null,
        authorId: user?.id || '',
        sessionId,
        author: {
          id: user?.id || '',
          firstName: user?.first_name || 'You',
          lastName: user?.last_name || '',
        },
        parentMessage: parentMsg
          ? { id: parentMsg.id, text: parentMsg.text, author: parentMsg.author }
          : undefined,
        isOptimistic: true,
        optimisticId,
      };

      setMessages((prev) => [...prev, optimisticMessage]);

      const payload: Record<string, string> = { sessionId, text: trimmedText, idempotencyKey };
      if (replyingToMessageId) payload.replyingToMessageId = replyingToMessageId;

      return new Promise((resolve) => {
        const timeoutId = setTimeout(() => {
          setIsSending(false);
          resolve(true);
        }, 5000);

        socket.emit('chat.message.send', payload, (response: SendMessageResponse) => {
          clearTimeout(timeoutId);
          setIsSending(false);

          if (response?.success) {
            if (response.messageId) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === optimisticId
                    ? { ...m, id: response.messageId!, optimisticId: undefined, isOptimistic: false }
                    : m,
                ),
              );
            }
            resolve(true);
          } else {
            const errorMsg =
              typeof response?.error === 'string'
                ? response.error
                : response?.error?.message || 'Failed to send message';
            setMessages((prev) => prev.filter((m) => m.id !== optimisticId));
            setError(errorMsg);
            resolve(false);
          }
        });
      });
    },
    [socket, isJoined, sessionId, user],
  );

  const deleteMessage = useCallback(
    async (messageId: string): Promise<boolean> => {
      if (!socket || !isJoined) return false;

      const currentMessages = messagesRef.current;
      const original = currentMessages.find((m) => m.id === messageId);
      const originalIndex = currentMessages.findIndex((m) => m.id === messageId);

      setMessages((prev) => prev.filter((m) => m.id !== messageId));

      return new Promise((resolve) => {
        socket.emit(
          'chat.message.delete',
          { messageId, idempotencyKey: generateUUID() },
          (response: SendMessageResponse) => {
            if (response?.success) {
              resolve(true);
            } else {
              if (original) {
                setMessages((prev) => {
                  const updated = [...prev];
                  updated.splice(originalIndex, 0, original);
                  return updated;
                });
              }
              resolve(false);
            }
          },
        );
      });
    },
    [socket, isJoined],
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    messages,
    isConnected,
    isJoined,
    chatOpen,
    isSending,
    error,
    currentUserId: user?.id,
    sendMessage,
    deleteMessage,
    clearError,
  };
}
