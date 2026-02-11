// Hook for managing live subtitle streaming with translation
// Ported from ../globalconnect/src/hooks/use-live-subtitles.ts

import { useState, useEffect, useCallback, useRef } from 'react';
import type { Socket } from 'socket.io-client';
import { useSubtitleStore } from '@/store/subtitle.store';

export interface SubtitleChunk {
  sessionId: string;
  text: string;
  language: string;
  duration: number; // ms
  speakerName?: string;
}

export interface ActiveSubtitle extends SubtitleChunk {
  id: string;
  expiresAt: number;
  translatedText?: string;
}

interface TranslationResponse {
  success: boolean;
  data?: {
    translatedText: string;
  };
}

interface LiveSubtitlesState {
  subtitles: ActiveSubtitle[];
  isConnected: boolean;
  isPaused: boolean;
  error: string | null;
}

interface UseLiveSubtitlesOptions {
  socket: Socket | null;
  sessionId: string;
  autoTranslate?: boolean;
}

// Generate UUID v4
const generateUUID = (): string => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
};

export function useLiveSubtitles({ socket, sessionId, autoTranslate = true }: UseLiveSubtitlesOptions) {
  const [state, setState] = useState<LiveSubtitlesState>({
    subtitles: [],
    isConnected: false,
    isPaused: false,
    error: null,
  });

  const { enabled, toggleEnabled, getEffectiveLanguage, showOriginalWithTranslation } = useSubtitleStore();

  const timeoutsRef = useRef<Map<string, NodeJS.Timeout>>(new Map());
  const translationCacheRef = useRef<Map<string, string>>(new Map());
  const pendingTranslationsRef = useRef<Set<string>>(new Set());

  const enabledRef = useRef<boolean>(enabled);
  const isPausedRef = useRef<boolean>(state.isPaused);

  const MAX_CACHE_SIZE = 500;

  useEffect(() => {
    enabledRef.current = enabled;
  }, [enabled]);

  useEffect(() => {
    isPausedRef.current = state.isPaused;
  }, [state.isPaused]);

  // Request translation
  const requestTranslation = useCallback(
    (subtitleId: string, text: string, sourceLanguage: string) => {
      if (!socket || !autoTranslate) return;

      const targetLanguage = getEffectiveLanguage();

      if (sourceLanguage === targetLanguage) return;

      const cacheKey = `${text}:${targetLanguage}`;
      const cached = translationCacheRef.current.get(cacheKey);

      if (translationCacheRef.current.size >= MAX_CACHE_SIZE) {
        const firstKey = translationCacheRef.current.keys().next().value;
        if (firstKey) translationCacheRef.current.delete(firstKey);
      }

      if (cached) {
        setState((prev) => ({
          ...prev,
          subtitles: prev.subtitles.map((s) => (s.id === subtitleId ? { ...s, translatedText: cached } : s)),
        }));
        return;
      }

      if (pendingTranslationsRef.current.has(cacheKey)) return;
      pendingTranslationsRef.current.add(cacheKey);

      socket.emit(
        'translation.request',
        {
          messageId: subtitleId,
          targetLanguage,
          text,
          sourceLanguage,
        },
        (response: TranslationResponse) => {
          pendingTranslationsRef.current.delete(cacheKey);

          if (response?.success && response.data?.translatedText) {
            const translatedText = response.data.translatedText;
            translationCacheRef.current.set(cacheKey, translatedText);

            setState((prev) => ({
              ...prev,
              subtitles: prev.subtitles.map((s) => (s.id === subtitleId ? { ...s, translatedText } : s)),
            }));
          }
        }
      );
    },
    [socket, autoTranslate, getEffectiveLanguage]
  );

  // Add subtitle
  const addSubtitle = useCallback(
    (chunk: SubtitleChunk) => {
      const id = generateUUID();
      const expiresAt = Date.now() + chunk.duration;

      const activeSubtitle: ActiveSubtitle = {
        ...chunk,
        id,
        expiresAt,
      };

      setState((prev) => ({
        ...prev,
        subtitles: [...prev.subtitles, activeSubtitle],
      }));

      const targetLanguage = getEffectiveLanguage();
      if (autoTranslate && chunk.language !== targetLanguage) {
        requestTranslation(id, chunk.text, chunk.language);
      }

      const timeout = setTimeout(() => {
        setState((prev) => ({
          ...prev,
          subtitles: prev.subtitles.filter((s) => s.id !== id),
        }));
        timeoutsRef.current.delete(id);
      }, chunk.duration);

      timeoutsRef.current.set(id, timeout);
    },
    [autoTranslate, getEffectiveLanguage, requestTranslation]
  );

  // Clear all subtitles
  const clearSubtitles = useCallback(() => {
    timeoutsRef.current.forEach((timeout) => clearTimeout(timeout));
    timeoutsRef.current.clear();

    setState((prev) => ({
      ...prev,
      subtitles: [],
    }));
  }, []);

  // Pause subtitle display
  const pause = useCallback(() => {
    setState((prev) => ({ ...prev, isPaused: true }));
  }, []);

  // Resume subtitle display
  const resume = useCallback(() => {
    setState((prev) => ({ ...prev, isPaused: false }));
  }, []);

  // Clear error
  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
  }, []);

  // Socket event listeners
  useEffect(() => {
    if (!socket || !sessionId) return;

    const handleConnect = () => {
      setState((prev) => ({ ...prev, isConnected: true, error: null }));
    };

    const handleDisconnect = () => {
      setState((prev) => ({ ...prev, isConnected: false }));
    };

    const handleSubtitleChunk = (chunk: SubtitleChunk) => {
      if (chunk.sessionId !== sessionId) return;

      if (enabledRef.current && !isPausedRef.current) {
        addSubtitle(chunk);
      }
    };

    const handleError = (error: { message: string }) => {
      setState((prev) => ({ ...prev, error: error.message }));
    };

    socket.on('connect', handleConnect);
    socket.on('disconnect', handleDisconnect);
    socket.on('subtitle.stream.chunk', handleSubtitleChunk);
    socket.on('systemError', handleError);

    setState((prev) => ({
      ...prev,
      isConnected: socket.connected,
    }));

    return () => {
      socket.off('connect', handleConnect);
      socket.off('disconnect', handleDisconnect);
      socket.off('subtitle.stream.chunk', handleSubtitleChunk);
      socket.off('systemError', handleError);

      timeoutsRef.current.forEach((timeout) => clearTimeout(timeout));
      timeoutsRef.current.clear();
    };
  }, [socket, sessionId, addSubtitle]);

  // Clear subtitles when disabled
  useEffect(() => {
    if (!enabled) {
      clearSubtitles();
    }
  }, [enabled, clearSubtitles]);

  return {
    // State
    subtitles: state.subtitles,
    isConnected: state.isConnected,
    isPaused: state.isPaused,
    error: state.error,
    enabled,
    showOriginalWithTranslation,

    // Actions
    toggleEnabled,
    pause,
    resume,
    clearSubtitles,
    clearError,
  };
}
