// Ported from ../globalconnect/src/store/auth.store.ts
// Adapted for React Native: uses expo-secure-store instead of localStorage/cookies

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { jwtDecode } from 'jwt-decode';
import { secureStorage } from '@/lib/secure-storage';

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  imageUrl?: string | null;
  role?: 'OWNER' | 'ADMIN' | 'MEMBER' | null;
}

interface JwtPayload {
  orgId: string;
  exp?: number;
}

interface AuthState {
  token: string | null;
  onboardingToken: string | null;
  user: User | null;
  orgId: string | null;
  isRefreshing: boolean;
  lastRefreshAttempt: number | null;

  setAuth: (token: string, user: User) => void;
  setOnboardingToken: (token: string | null) => void;
  logout: () => void;
  updateUser: (newUserData: Partial<User>) => void;
  isTokenExpired: () => boolean;
  setIsRefreshing: (isRefreshing: boolean) => void;
  getTokenExpiry: () => number | null;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      onboardingToken: null,
      user: null,
      orgId: null,
      isRefreshing: false,
      lastRefreshAttempt: null,

      updateUser: (newUserData) => {
        const currentUser = get().user;
        if (currentUser) {
          set({ user: { ...currentUser, ...newUserData } });
        }
      },

      setAuth: (token, user) => {
        try {
          const decodedPayload = jwtDecode<JwtPayload>(token);
          const orgId = decodedPayload.orgId || null;

          set({
            token,
            user,
            orgId,
            onboardingToken: null,
            isRefreshing: false,
            lastRefreshAttempt: Date.now(),
          });
        } catch (error) {
          console.error('[AuthStore] Failed to decode token:', error);
          set({
            token: null,
            user: null,
            orgId: null,
            onboardingToken: null,
            isRefreshing: false,
          });
        }
      },

      setOnboardingToken: (token) => set({ onboardingToken: token }),

      logout: () => {
        set({
          token: null,
          user: null,
          orgId: null,
          onboardingToken: null,
          isRefreshing: false,
          lastRefreshAttempt: null,
        });
      },

      setIsRefreshing: (isRefreshing) => set({ isRefreshing }),

      getTokenExpiry: () => {
        const token = get().token;
        if (!token) return null;

        try {
          const decoded = jwtDecode<JwtPayload>(token);
          return decoded.exp ? decoded.exp * 1000 : null;
        } catch {
          return null;
        }
      },

      isTokenExpired: () => {
        const token = get().token;
        if (!token) return true;

        try {
          const decoded = jwtDecode<JwtPayload>(token);
          if (!decoded.exp) return false;

          const expiresAt = decoded.exp * 1000;
          const bufferMs = 60 * 1000;
          return Date.now() >= expiresAt - bufferMs;
        } catch {
          return true;
        }
      },
    }),
    {
      name: 'auth-storage',
      storage: createJSONStorage(() => secureStorage),
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        orgId: state.orgId,
      }),
    },
  ),
);

export function getAuthState() {
  return useAuthStore.getState();
}

export function isAuthenticated(): boolean {
  const state = useAuthStore.getState();
  return !!state.token && !state.isTokenExpired();
}

export function isOrganizer(): boolean {
  const state = useAuthStore.getState();
  return !!state.token && !!state.orgId;
}
