// Design tokens extracted from the web app's globals.css HSL variables
// Converted to hex for React Native compatibility

export const colors = {
  // Primary brand colors
  primary: {
    gold: '#F5C542',
    goldLight: '#F7D06B',
    goldDark: '#D4A017',
    navy: '#132144',
    navyLight: '#1E3464',
    navyDark: '#0C1A38',
  },

  // Neutral palette
  neutral: {
    50: '#FAFAFA',
    100: '#F4F4F5',
    200: '#E4E4E7',
    300: '#D4D4D8',
    400: '#A1A1AA',
    500: '#71717A',
    600: '#52525B',
    700: '#3F3F46',
    800: '#27272A',
    900: '#18181B',
    950: '#09090B',
  },

  // Semantic colors
  success: '#16A34A',
  successLight: '#DCFCE7',
  warning: '#F59E0B',
  warningLight: '#FEF3C7',
  destructive: '#DC2626',
  destructiveLight: '#FEE2E2',
  info: '#3B82F6',
  infoLight: '#DBEAFE',

  // Background & surface
  background: '#FFFFFF',
  foreground: '#132144',
  card: '#FFFFFF',
  cardForeground: '#132144',
  border: '#E4E4E7',
  input: '#E4E4E7',
  ring: '#F5C542',

  // Dark mode
  dark: {
    background: '#132144',
    foreground: '#F4F4F5',
    card: '#1E3464',
    cardForeground: '#F4F4F5',
    border: '#2D4A7A',
    input: '#2D4A7A',
    muted: '#1E3464',
    mutedForeground: '#A3A3B5',
  },
} as const;

export type ColorToken = typeof colors;
