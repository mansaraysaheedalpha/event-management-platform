import React from 'react';
import {
  ThemeProvider as NavThemeProvider,
  DefaultTheme,
  DarkTheme,
} from '@react-navigation/native';
import { useTheme } from './useTheme';
import { colors } from './colors';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const { isDark, colors: c } = useTheme();

  const navigationTheme = isDark
    ? {
        ...DarkTheme,
        colors: {
          ...DarkTheme.colors,
          primary: colors.primary.gold,
          background: c.background,
          card: c.card,
          text: c.foreground,
          border: c.border,
          notification: colors.destructive,
        },
      }
    : {
        ...DefaultTheme,
        colors: {
          ...DefaultTheme.colors,
          primary: colors.primary.gold,
          background: c.background,
          card: c.card,
          text: c.foreground,
          border: c.border,
          notification: colors.destructive,
        },
      };

  return (
    <NavThemeProvider value={navigationTheme}>{children}</NavThemeProvider>
  );
}
