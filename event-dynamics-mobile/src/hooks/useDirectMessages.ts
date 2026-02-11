// Hook for direct messaging via Socket.IO
// Ported from ../globalconnect/src/hooks/use-direct-messages.ts

import { useState, useCallback, useRef, useEffect } from 'react';
import { io, Socket } from 'socket.io-client';
import { useAuthStore } from '@/store/auth.store';
import { env } from '@/lib/env';
import type { DirectMessage, Conversation, MessageStatus } from '@/types/networking';

const MAX_MESSAGE_LENGTH = 2000;
const RATE_LIMIT_PER_SEC = 2;
const BURST_LIMIT = 5;
const BURST_WINDOW_MS = 10_000;

/** Generate a UUID for idempotency */
function generateId(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

interface UseDirectMessagesOptions {
  eventId?: string;
  autoConnect?: boolean;
}

export function useDirectMessages(options: UseDirectMessagesOptions = {}) {
  const { eventId, autoConnect = true } = options;
  const [isConnected, setIsConnected] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<DirectMessage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isTyping, setIsTyping] = useState<Record<string, boolean>>({});

  const socketRef = useRef<Socket | null>(null);
  const messageTimes = useRef<number[]>([]);
  const { token, user } = useAuthStore();

  // Connect to socket
  useEffect(() => {
    if (!autoConnect || !token) return;

    const realtimeUrl = `${env.REALTIME_URL}/events`;
    const newSocket = io(realtimeUrl, {
      auth: { token: `Bearer ${token}` },
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 10000,
      timeout: 20000,
    });

    socketRef.current = newSocket;

    newSocket.on('connect', () => {
      setIsConnected(true);
      setError(null);
    });

    newSocket.on('connectionAcknowledged', () => {
      // Load conversations
      newSocket.emit('dm.conversations.get', {}, (response: {
        success: boolean;
        conversations?: Conversation[];
        error?: string;
      }) => {
        if (response.success && response.conversations) {
          setConversations(response.conversations);
        }
      });
    });

    newSocket.on('disconnect', () => {
      setIsConnected(false);
    });

    newSocket.on('connect_error', (err: Error) => {
      setError(err.message);
      setIsConnected(false);
    });

    // Incoming message
    newSocket.on('dm.new', (message: DirectMessage) => {
      // Update messages if in active conversation
      setMessages(prev => {
        if (prev.length > 0 && prev[0]?.conversationId === message.conversationId) {
          // Deduplicate
          if (prev.some(m => m.id === message.id)) return prev;
          return [...prev, message];
        }
        return prev;
      });

      // Update conversation list
      setConversations(prev => {
        const idx = prev.findIndex(c => c.id === message.conversationId);
        if (idx >= 0) {
          const updated = [...prev];
          updated[idx] = {
            ...updated[idx],
            lastMessage: message,
            unreadCount: updated[idx].unreadCount + (message.senderId !== user?.id ? 1 : 0),
            updatedAt: message.timestamp,
          };
          // Move to top
          const [conv] = updated.splice(idx, 1);
          return [conv, ...updated];
        }
        return prev;
      });

      // Auto mark as delivered
      if (message.senderId !== user?.id) {
        newSocket.emit('dm.delivered', {
          messageId: message.id,
          idempotencyKey: generateId(),
        });
      }
    });

    // Delivery receipt
    newSocket.on('dm.delivery_update', (data: {
      messageId: string;
      conversationId: string;
      isDelivered: boolean;
    }) => {
      setMessages(prev =>
        prev.map(m => m.id === data.messageId ? { ...m, isDelivered: true, status: 'delivered' as MessageStatus } : m),
      );
    });

    // Read receipt
    newSocket.on('dm.read_update', (data: {
      messageId: string;
      conversationId: string;
      isRead: boolean;
    }) => {
      setMessages(prev =>
        prev.map(m => m.id === data.messageId ? { ...m, isRead: true, status: 'read' as MessageStatus } : m),
      );
    });

    // Message edited
    newSocket.on('dm.message.updated', (updated: DirectMessage) => {
      setMessages(prev =>
        prev.map(m => m.id === updated.id ? updated : m),
      );
    });

    // Message deleted
    newSocket.on('dm.message.deleted', (data: { messageId: string }) => {
      setMessages(prev => prev.filter(m => m.id !== data.messageId));
    });

    // Typing indicator
    newSocket.on('dm.typing', (data: { conversationId: string; userId: string; isTyping: boolean }) => {
      setIsTyping(prev => ({ ...prev, [data.conversationId]: data.isTyping }));
      if (data.isTyping) {
        setTimeout(() => {
          setIsTyping(prev => ({ ...prev, [data.conversationId]: false }));
        }, 3000);
      }
    });

    newSocket.on('systemError', (data: { message: string }) => {
      setError(data.message);
    });

    return () => {
      socketRef.current = null;
      newSocket.removeAllListeners();
      newSocket.disconnect();
    };
  }, [autoConnect, token, user?.id]);

  // Rate limiting check
  const canSendMessage = useCallback((): boolean => {
    const now = Date.now();
    const recent = messageTimes.current.filter(t => now - t < 1000);
    const burst = messageTimes.current.filter(t => now - t < BURST_WINDOW_MS);
    return recent.length < RATE_LIMIT_PER_SEC && burst.length < BURST_LIMIT;
  }, []);

  const sendMessage = useCallback((recipientId: string, text: string): { success: boolean; messageId?: string } => {
    const socket = socketRef.current;
    if (!socket?.connected || !text.trim() || text.length > MAX_MESSAGE_LENGTH) {
      return { success: false };
    }
    if (!canSendMessage()) {
      return { success: false };
    }

    const messageId = generateId();
    const idempotencyKey = generateId();
    messageTimes.current.push(Date.now());

    // Optimistic update
    const optimisticMessage: DirectMessage = {
      id: messageId,
      text: text.trim(),
      timestamp: new Date().toISOString(),
      senderId: user?.id || '',
      conversationId: activeConversation?.id || `temp-${recipientId}`,
      isDelivered: false,
      isRead: false,
      status: 'sending',
    };

    setMessages(prev => [...prev, optimisticMessage]);

    socket.emit('dm.send', {
      recipientId,
      text: text.trim(),
      eventId,
      idempotencyKey,
    }, (response: { success: boolean; messageId?: string; timestamp?: string; error?: string }) => {
      if (response.success) {
        setMessages(prev =>
          prev.map(m => m.id === messageId
            ? { ...m, id: response.messageId || messageId, status: 'sent' as MessageStatus, timestamp: response.timestamp || m.timestamp }
            : m),
        );
      } else {
        setMessages(prev =>
          prev.map(m => m.id === messageId ? { ...m, status: 'failed' as MessageStatus } : m),
        );
      }
    });

    return { success: true, messageId };
  }, [user?.id, eventId, activeConversation?.id, canSendMessage]);

  const markAsDelivered = useCallback((messageId: string) => {
    socketRef.current?.emit('dm.delivered', { messageId, idempotencyKey: generateId() });
  }, []);

  const markAsRead = useCallback((messageId: string) => {
    socketRef.current?.emit('dm.read', { messageId, idempotencyKey: generateId() });
    setMessages(prev =>
      prev.map(m => m.id === messageId ? { ...m, isRead: true, status: 'read' as MessageStatus } : m),
    );
  }, []);

  const editMessage = useCallback((messageId: string, newText: string): boolean => {
    const socket = socketRef.current;
    if (!socket?.connected || !newText.trim() || newText.length > MAX_MESSAGE_LENGTH) return false;

    socket.emit('dm.message.edit', {
      messageId,
      newText: newText.trim(),
      idempotencyKey: generateId(),
    }, (response: { success: boolean; error?: string }) => {
      if (response.success) {
        setMessages(prev =>
          prev.map(m => m.id === messageId ? { ...m, text: newText.trim(), isEdited: true, editedAt: new Date().toISOString() } : m),
        );
      }
    });
    return true;
  }, []);

  const deleteMessage = useCallback((messageId: string): boolean => {
    const socket = socketRef.current;
    if (!socket?.connected) return false;

    socket.emit('dm.message.delete', {
      messageId,
      idempotencyKey: generateId(),
    }, (response: { success: boolean; error?: string }) => {
      if (response.success) {
        setMessages(prev => prev.filter(m => m.id !== messageId));
      }
    });
    return true;
  }, []);

  const loadMessages = useCallback((conversationId: string) => {
    const socket = socketRef.current;
    if (!socket?.connected) return;

    socket.emit('dm.messages.get', { conversationId, limit: 50 }, (response: {
      success: boolean;
      messages?: DirectMessage[];
      error?: string;
    }) => {
      if (response.success && response.messages) {
        setMessages(response.messages);
      }
    });
  }, []);

  const retryMessage = useCallback((messageId: string) => {
    const msg = messages.find(m => m.id === messageId);
    if (!msg || msg.status !== 'failed') return;

    const recipientId = activeConversation?.recipientId;
    if (!recipientId) return;

    // Remove failed message and resend
    setMessages(prev => prev.filter(m => m.id !== messageId));
    sendMessage(recipientId, msg.text);
  }, [messages, activeConversation?.recipientId, sendMessage]);

  const getTotalUnreadCount = useCallback((): number => {
    return conversations.reduce((sum, c) => sum + c.unreadCount, 0);
  }, [conversations]);

  const setActiveConversationAndLoad = useCallback((conversation: Conversation | null) => {
    setActiveConversation(conversation);
    if (conversation) {
      loadMessages(conversation.id);
      // Mark unread as read
      setConversations(prev =>
        prev.map(c => c.id === conversation.id ? { ...c, unreadCount: 0 } : c),
      );
    } else {
      setMessages([]);
    }
  }, [loadMessages]);

  const clearError = useCallback(() => setError(null), []);

  return {
    isConnected,
    conversations,
    activeConversation,
    messages,
    error,
    isTyping,
    sendMessage,
    markAsDelivered,
    markAsRead,
    editMessage,
    deleteMessage,
    setActiveConversation: setActiveConversationAndLoad,
    loadMessages,
    retryMessage,
    canSendMessage,
    getTotalUnreadCount,
    clearError,
  };
}
