import { useColorScheme } from 'react-native';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { colors } from './colors';

type ThemePreference = 'system' | 'light' | 'dark';
type ResolvedTheme = 'light' | 'dark';

interface ThemeState {
  preference: ThemePreference;
  setPreference: (pref: ThemePreference) => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      preference: 'system',
      setPreference: (preference) => set({ preference }),
    }),
    {
      name: 'theme-storage',
      storage: createJSONStorage(() => AsyncStorage),
    },
  ),
);

export function useTheme() {
  const systemScheme = useColorScheme();
  const preference = useThemeStore((s) => s.preference);

  const resolvedTheme: ResolvedTheme =
    preference === 'system'
      ? (systemScheme ?? 'light')
      : preference;

  const isDark = resolvedTheme === 'dark';

  return {
    isDark,
    theme: resolvedTheme,
    colors: {
      // Surface colors that change with theme
      background: isDark ? colors.dark.background : colors.background,
      foreground: isDark ? colors.dark.foreground : colors.foreground,
      card: isDark ? colors.dark.card : colors.card,
      cardForeground: isDark ? colors.dark.cardForeground : colors.cardForeground,
      border: isDark ? colors.dark.border : colors.border,
      input: isDark ? colors.dark.input : colors.input,
      muted: isDark ? colors.dark.muted : colors.neutral[100],
      mutedForeground: isDark ? colors.dark.mutedForeground : colors.neutral[500],

      // Brand colors (same in both themes)
      primary: colors.primary,
      neutral: colors.neutral,
      ring: colors.ring,

      // Semantic colors (same in both themes)
      success: colors.success,
      successLight: colors.successLight,
      warning: colors.warning,
      warningLight: colors.warningLight,
      destructive: colors.destructive,
      destructiveLight: colors.destructiveLight,
      info: colors.info,
      infoLight: colors.infoLight,
    },
  };
}
