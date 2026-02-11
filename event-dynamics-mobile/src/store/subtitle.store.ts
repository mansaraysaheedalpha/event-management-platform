// Zustand store for subtitle preferences
// Ported from ../globalconnect/src/store/subtitle.store.ts

import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import AsyncStorage from '@react-native-async-storage/async-storage';

export type SubtitleLanguage = 'en' | 'es' | 'fr' | 'de' | 'zh' | 'ja' | 'auto';
export type SubtitleFontSize = 'small' | 'medium' | 'large';
export type SubtitlePosition = 'top' | 'bottom';

interface SubtitleStore {
  enabled: boolean;
  language: SubtitleLanguage;
  fontSize: SubtitleFontSize;
  backgroundColor: string;
  textColor: string;
  position: SubtitlePosition;
  showOriginalWithTranslation: boolean;
  toggleEnabled: () => void;
  setLanguage: (lang: SubtitleLanguage) => void;
  setFontSize: (size: SubtitleFontSize) => void;
  setBackgroundColor: (color: string) => void;
  setTextColor: (color: string) => void;
  setPosition: (pos: SubtitlePosition) => void;
  setShowOriginalWithTranslation: (show: boolean) => void;
  getEffectiveLanguage: () => SubtitleLanguage;
}

export const useSubtitleStore = create<SubtitleStore>()(
  persist(
    (set, get) => ({
      enabled: false,
      language: 'auto',
      fontSize: 'medium',
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      textColor: '#FFFFFF',
      position: 'bottom',
      showOriginalWithTranslation: false,

      toggleEnabled: () => set((state) => ({ enabled: !state.enabled })),

      setLanguage: (lang) => set({ language: lang }),

      setFontSize: (size) => set({ fontSize: size }),

      setBackgroundColor: (color) => set({ backgroundColor: color }),

      setTextColor: (color) => set({ textColor: color }),

      setPosition: (pos) => set({ position: pos }),

      setShowOriginalWithTranslation: (show) => set({ showOriginalWithTranslation: show }),

      getEffectiveLanguage: () => {
        const { language } = get();
        if (language === 'auto') {
          // Detect device language - default to English for now
          // In production, use expo-localization to detect device language
          return 'en';
        }
        return language;
      },
    }),
    {
      name: 'subtitle-preferences',
      storage: createJSONStorage(() => AsyncStorage),
    }
  )
);

// Subtitle font sizes in pixels
export const SUBTITLE_FONT_SIZES: Record<SubtitleFontSize, number> = {
  small: 14,
  medium: 16,
  large: 20,
};
