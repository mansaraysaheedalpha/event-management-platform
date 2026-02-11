// Zustand store for managing active video session state and mini player

import { create } from 'zustand';
import { Dimensions } from 'react-native';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');

interface VideoSessionStore {
  // Active call state
  activeSessionId: string | null;
  activeEventId: string | null;
  activeSessionTitle: string | null;

  // Mini player state
  isMinimized: boolean;
  miniPlayerPosition: { x: number; y: number };

  // Actions
  setActiveSession: (sessionId: string, eventId: string, sessionTitle: string) => void;
  clearActiveSession: () => void;
  minimizePlayer: () => void;
  maximizePlayer: () => void;
  dismissMiniPlayer: () => void;
  setMiniPlayerPosition: (x: number, y: number) => void;
}

export const useVideoSessionStore = create<VideoSessionStore>()((set) => ({
  activeSessionId: null,
  activeEventId: null,
  activeSessionTitle: null,
  isMinimized: false,
  miniPlayerPosition: {
    x: SCREEN_WIDTH - 140,
    y: SCREEN_HEIGHT - 240,
  },

  setActiveSession: (sessionId, eventId, sessionTitle) =>
    set({
      activeSessionId: sessionId,
      activeEventId: eventId,
      activeSessionTitle: sessionTitle,
      isMinimized: false,
    }),

  clearActiveSession: () =>
    set({
      activeSessionId: null,
      activeEventId: null,
      activeSessionTitle: null,
      isMinimized: false,
    }),

  minimizePlayer: () => set({ isMinimized: true }),

  maximizePlayer: () => set({ isMinimized: false }),

  dismissMiniPlayer: () =>
    set({
      isMinimized: false,
      activeSessionId: null,
      activeEventId: null,
      activeSessionTitle: null,
    }),

  setMiniPlayerPosition: (x, y) =>
    set({ miniPlayerPosition: { x, y } }),
}));
