// Subtitle overlay component for displaying live captions
// Ported from ../globalconnect/src/components/features/subtitles/SubtitleOverlay.tsx

import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Animated, { FadeIn, FadeOut } from 'react-native-reanimated';
import { useSubtitleStore, SUBTITLE_FONT_SIZES } from '@/store/subtitle.store';
import type { ActiveSubtitle } from '@/hooks/useLiveSubtitles';

interface SubtitleOverlayProps {
  subtitles: ActiveSubtitle[];
  style?: object;
}

export function SubtitleOverlay({ subtitles, style }: SubtitleOverlayProps) {
  const { enabled, fontSize, backgroundColor, textColor, position, showOriginalWithTranslation } = useSubtitleStore();

  if (!enabled || subtitles.length === 0) {
    return null;
  }

  const fontSizeValue = SUBTITLE_FONT_SIZES[fontSize];

  return (
    <View
      style={[
        styles.container,
        position === 'bottom' ? styles.positionBottom : styles.positionTop,
        style,
      ]}
      pointerEvents="none"
    >
      {subtitles.map((subtitle) => (
        <Animated.View
          key={subtitle.id}
          entering={FadeIn.duration(200)}
          exiting={FadeOut.duration(200)}
          style={styles.subtitleContainer}
        >
          <View
            style={[
              styles.subtitle,
              {
                backgroundColor,
              },
            ]}
          >
            {subtitle.translatedText ? (
              <>
                <Text
                  style={[
                    styles.subtitleText,
                    {
                      color: textColor,
                      fontSize: fontSizeValue,
                    },
                  ]}
                >
                  {subtitle.translatedText}
                </Text>
                {showOriginalWithTranslation && (
                  <Text
                    style={[
                      styles.originalText,
                      {
                        color: textColor,
                        fontSize: fontSizeValue * 0.75,
                      },
                    ]}
                  >
                    {subtitle.text}
                  </Text>
                )}
              </>
            ) : (
              <Text
                style={[
                  styles.subtitleText,
                  {
                    color: textColor,
                    fontSize: fontSizeValue,
                  },
                ]}
              >
                {subtitle.text}
              </Text>
            )}
          </View>
        </Animated.View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: 0,
    right: 0,
    alignItems: 'center',
    paddingHorizontal: 16,
    gap: 4,
  },
  positionBottom: {
    bottom: 80, // Above video controls
  },
  positionTop: {
    top: 16,
  },
  subtitleContainer: {
    maxWidth: '90%',
  },
  subtitle: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.8,
    shadowRadius: 4,
    elevation: 8,
  },
  subtitleText: {
    textAlign: 'center',
    fontWeight: '500',
  },
  originalText: {
    textAlign: 'center',
    marginTop: 4,
    opacity: 0.7,
    fontStyle: 'italic',
  },
});
