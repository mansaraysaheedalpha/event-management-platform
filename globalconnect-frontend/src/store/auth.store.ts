// src/store/auth.store.ts
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { jwtDecode } from "jwt-decode";

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  imageUrl?: string | null;
}

interface JwtPayload {
  orgId: string;
}

interface AuthState {
  token: string | null;
  onboardingToken: string | null; // <-- ADD THIS
  user: User | null;
  orgId: string | null;

  setAuth: (token: string, user: User) => void;
  setOnboardingToken: (token: string | null) => void;
  logout: () => void;
  updateUser: (newUserData: Partial<User>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      onboardingToken: null, // <-- Initialize
      user: null,
      orgId: null,

      updateUser: (newUserData) => {
        const currentUser = get().user;
        if (currentUser) {
          set({ user: { ...currentUser, ...newUserData } });
        }
      },
      setAuth: (token, user) => {
        const decodedPayload = jwtDecode<JwtPayload>(token);
        const orgId = decodedPayload.orgId;
        // When a full login happens, clear any temporary tokens
        set({ token, user, orgId, onboardingToken: null });
      },

      // Method to specifically handle the temporary token
      setOnboardingToken: (token) => set({ onboardingToken: token }),

      logout: () =>
        set({ token: null, user: null, orgId: null, onboardingToken: null }),
    }),
    {
      name: "auth-storage",
      storage: createJSONStorage(() => localStorage),
      // Only persist the main token and user, not the temporary one
      partialize: (state) => ({
        token: state.token,
        user: state.user,
        orgId: state.orgId,
      }),
    }
  )
);
