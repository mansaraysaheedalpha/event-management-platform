// Video tile component for displaying individual participant video
// Ported from ../globalconnect/src/components/features/breakout/video/VideoTile.tsx

import React, { useEffect, useRef, useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import type { DailyParticipant } from '@daily-co/react-native-daily-js';
import { DailyMediaView } from '@daily-co/react-native-daily-js';
import { colors } from '@/theme/colors';
import { typography } from '@/theme/typography';

interface VideoTileProps {
  participant: DailyParticipant;
  isLocal?: boolean;
  isLarge?: boolean;
  isPinned?: boolean;
  style?: object;
}

// Generate consistent gradient from participant name
function getAvatarGradient(name: string): string[] {
  const gradients = [
    ['#7C3AED', '#4F46E5'], // violet to indigo
    ['#2563EB', '#06B6D4'], // blue to cyan
    ['#059669', '#14B8A6'], // emerald to teal
    ['#F97316', '#FB923C'], // orange to rose
    ['#DB2777', '#A855F7'], // pink to purple
    ['#F59E0B', '#F97316'], // amber to orange
    ['#06B6D4', '#2563EB'], // cyan to blue
    ['#FB7185', '#DB2777'], // rose to pink
    ['#14B8A6', '#059669'], // teal to emerald
    ['#6366F1', '#7C3AED'], // indigo to violet
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return gradients[Math.abs(hash) % gradients.length];
}

function getInitials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || '')
    .join('');
}

export function VideoTile({ participant, isLocal = false, isLarge = false, isPinned = false, style }: VideoTileProps) {
  const hasVideo = participant.video;
  const hasAudio = participant.audio;
  const hasScreen = participant.screen;
  const userName = participant.user_name || (isLocal ? 'You' : 'Participant');
  const initials = useMemo(() => getInitials(userName), [userName]);
  const gradientColors = useMemo(() => getAvatarGradient(userName), [userName]);

  const videoTrack = participant.tracks?.video?.persistentTrack;
  const screenTrack = participant.tracks?.screenVideo?.persistentTrack;

  return (
    <View style={[styles.container, isLarge && styles.containerLarge, isPinned && styles.containerPinned, style]}>
      {/* Screen share (takes priority) */}
      {hasScreen && !!screenTrack && (
        <DailyMediaView
          videoTrack={screenTrack}
          mirror={false}
          objectFit="contain"
          style={styles.video}
        />
      )}

      {/* Camera video */}
      {hasVideo && !hasScreen && !!videoTrack ? (
        <DailyMediaView
          videoTrack={videoTrack}
          mirror={isLocal}
          objectFit="cover"
          style={styles.video}
        />
      ) : (
        !hasScreen && (
          <View style={styles.avatarContainer}>
            <View
              style={[
                styles.avatar,
                isLarge ? styles.avatarLarge : styles.avatarSmall,
                { backgroundColor: gradientColors[0] },
              ]}
            >
              <Text style={[styles.initials, isLarge ? styles.initialsLarge : styles.initialsSmall]}>{initials || '?'}</Text>
            </View>
          </View>
        )
      )}

      {/* Small camera preview when screen sharing */}
      {hasScreen && hasVideo && !!videoTrack && (
        <View style={[styles.pipContainer, isLarge ? styles.pipLarge : styles.pipSmall]}>
          <DailyMediaView videoTrack={videoTrack} mirror={isLocal} objectFit="cover" style={styles.pipVideo} />
        </View>
      )}

      {/* Pinned indicator */}
      {isPinned && (
        <View style={styles.pinnedBadge}>
          <Text style={styles.pinnedText}>📌 Pinned</Text>
        </View>
      )}

      {/* "You" badge for local participant */}
      {isLocal && !isPinned && (
        <View style={styles.youBadge}>
          <Text style={styles.youText}>You</Text>
        </View>
      )}

      {/* Participant info overlay */}
      <View style={[styles.infoOverlay, isLarge ? styles.infoOverlayLarge : styles.infoOverlaySmall]}>
        <View style={styles.infoContent}>
          <View style={styles.nameContainer}>
            <Text
              style={[styles.userName, isLarge ? styles.userNameLarge : styles.userNameSmall]}
              numberOfLines={1}
            >
              {userName}
            </Text>
            {hasScreen && (
              <View style={styles.sharingBadge}>
                <Text style={styles.sharingText}>🖥️ Sharing</Text>
              </View>
            )}
          </View>

          {/* Audio/Video indicators */}
          <View style={styles.indicators}>
            <View style={[styles.indicator, hasAudio ? styles.indicatorActive : styles.indicatorMuted]}>
              <Text style={styles.indicatorIcon}>{hasAudio ? '🎤' : '🔇'}</Text>
            </View>
            <View style={[styles.indicator, hasVideo ? styles.indicatorActive : styles.indicatorMuted]}>
              <Text style={styles.indicatorIcon}>{hasVideo ? '📹' : '📵'}</Text>
            </View>
          </View>
        </View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'relative',
    backgroundColor: colors.neutral[900],
    borderRadius: 12,
    overflow: 'hidden',
    aspectRatio: 16 / 9,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  containerLarge: {
    borderRadius: 16,
  },
  containerPinned: {
    borderWidth: 2,
    borderColor: colors.info,
  },
  video: {
    position: 'absolute',
    width: '100%',
    height: '100%',
  },
  avatarContainer: {
    position: 'absolute',
    width: '100%',
    height: '100%',
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.neutral[900],
  },
  avatar: {
    borderRadius: 9999,
    justifyContent: 'center',
    alignItems: 'center',
  },
  avatarSmall: {
    width: 56,
    height: 56,
  },
  avatarLarge: {
    width: 96,
    height: 96,
  },
  initials: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  initialsSmall: {
    fontSize: 20,
  },
  initialsLarge: {
    fontSize: 36,
  },
  pipContainer: {
    position: 'absolute',
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.2)',
    backgroundColor: colors.neutral[900],
  },
  pipSmall: {
    bottom: 48,
    right: 8,
    width: 80,
    height: 64,
  },
  pipLarge: {
    bottom: 80,
    right: 16,
    width: 144,
    height: 112,
  },
  pipVideo: {
    width: '100%',
    height: '100%',
  },
  pinnedBadge: {
    position: 'absolute',
    top: 12,
    left: 12,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 9999,
    backgroundColor: 'rgba(59, 130, 246, 0.8)',
  },
  pinnedText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '500',
  },
  youBadge: {
    position: 'absolute',
    top: 12,
    left: 12,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 9999,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
  },
  youText: {
    color: 'rgba(255, 255, 255, 0.9)',
    fontSize: 12,
    fontWeight: '500',
  },
  infoOverlay: {
    position: 'absolute',
    bottom: 0,
    left: 0,
    right: 0,
    paddingTop: 32,
  },
  infoOverlaySmall: {
    padding: 8,
  },
  infoOverlayLarge: {
    padding: 12,
  },
  infoContent: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    paddingHorizontal: 8,
    paddingVertical: 6,
    borderRadius: 8,
  },
  nameContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    flex: 1,
    minWidth: 0,
  },
  userName: {
    color: '#FFFFFF',
    fontWeight: '500',
    flexShrink: 1,
  },
  userNameSmall: {
    fontSize: 12,
  },
  userNameLarge: {
    fontSize: 14,
  },
  sharingBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 9999,
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
  },
  sharingText: {
    color: '#10B981',
    fontSize: 10,
    fontWeight: '500',
  },
  indicators: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  indicator: {
    width: 24,
    height: 24,
    borderRadius: 9999,
    justifyContent: 'center',
    alignItems: 'center',
  },
  indicatorActive: {
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
  },
  indicatorMuted: {
    backgroundColor: 'rgba(220, 38, 38, 0.8)',
  },
  indicatorIcon: {
    fontSize: 12,
  },
});
