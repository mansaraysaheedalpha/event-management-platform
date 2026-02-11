// Floating mini player that appears when navigating away from an active video session
// Supports drag to reposition and swipe down to dismiss

import React, { useCallback } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Dimensions } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
} from 'react-native-reanimated';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import { useVideoSessionStore } from '@/store/videoSession.store';
import { useDailyCall } from '@/providers/DailyProvider';
import { colors } from '@/theme/colors';

const { width: SCREEN_WIDTH, height: SCREEN_HEIGHT } = Dimensions.get('window');
const MINI_PLAYER_WIDTH = 130;
const MINI_PLAYER_HEIGHT = 90;
const DISMISS_THRESHOLD = 80;

interface MiniPlayerProps {
  onMaximize: () => void;
}

export function MiniPlayer({ onMaximize }: MiniPlayerProps) {
  const { isMinimized, activeSessionTitle, miniPlayerPosition, setMiniPlayerPosition, dismissMiniPlayer } =
    useVideoSessionStore();

  const { isMicOn, toggleMic, leaveCall } = useDailyCall();

  const translateX = useSharedValue(miniPlayerPosition.x);
  const translateY = useSharedValue(miniPlayerPosition.y);
  const scale = useSharedValue(1);
  const opacity = useSharedValue(1);

  const contextX = useSharedValue(0);
  const contextY = useSharedValue(0);

  const handleDismiss = useCallback(() => {
    leaveCall();
    dismissMiniPlayer();
  }, [leaveCall, dismissMiniPlayer]);

  const handleMaximize = useCallback(() => {
    onMaximize();
  }, [onMaximize]);

  // Pan gesture for dragging
  const panGesture = Gesture.Pan()
    .onStart(() => {
      contextX.value = translateX.value;
      contextY.value = translateY.value;
      scale.value = withSpring(1.05);
    })
    .onUpdate((event) => {
      translateX.value = contextX.value + event.translationX;
      translateY.value = contextY.value + event.translationY;

      // Fade out when dragging down past threshold
      if (event.translationY > DISMISS_THRESHOLD) {
        opacity.value = withTiming(0.5);
      } else {
        opacity.value = withTiming(1);
      }
    })
    .onEnd((event) => {
      scale.value = withSpring(1);

      // Dismiss if swiped down far enough
      if (event.translationY > DISMISS_THRESHOLD) {
        opacity.value = withTiming(0, { duration: 200 });
        runOnJS(handleDismiss)();
        return;
      }

      // Snap to edges
      const targetX =
        translateX.value + MINI_PLAYER_WIDTH / 2 > SCREEN_WIDTH / 2
          ? SCREEN_WIDTH - MINI_PLAYER_WIDTH - 12
          : 12;

      // Clamp Y within screen bounds
      const targetY = Math.max(60, Math.min(translateY.value, SCREEN_HEIGHT - MINI_PLAYER_HEIGHT - 120));

      translateX.value = withSpring(targetX);
      translateY.value = withSpring(targetY);

      runOnJS(setMiniPlayerPosition)(targetX, targetY);
      opacity.value = withTiming(1);
    });

  // Tap gesture for maximizing
  const tapGesture = Gesture.Tap().onEnd(() => {
    runOnJS(handleMaximize)();
  });

  const composedGestures = Gesture.Race(panGesture, tapGesture);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translateX.value },
      { translateY: translateY.value },
      { scale: scale.value },
    ],
    opacity: opacity.value,
  }));

  if (!isMinimized || !activeSessionTitle) {
    return null;
  }

  return (
    <GestureDetector gesture={composedGestures}>
      <Animated.View style={[styles.container, animatedStyle]}>
        {/* Video placeholder (dark background with session info) */}
        <View style={styles.videoPreview}>
          <View style={styles.liveBadge}>
            <View style={styles.liveDot} />
            <Text style={styles.liveText}>LIVE</Text>
          </View>
          <Text style={styles.sessionTitle} numberOfLines={1}>
            {activeSessionTitle}
          </Text>
        </View>

        {/* Mini controls */}
        <View style={styles.controls}>
          <TouchableOpacity
            style={[styles.miniButton, !isMicOn && styles.miniButtonMuted]}
            onPress={toggleMic}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Text style={styles.miniButtonIcon}>{isMicOn ? '🎤' : '🔇'}</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[styles.miniButton, styles.miniButtonClose]}
            onPress={handleDismiss}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <Text style={styles.miniButtonIcon}>✕</Text>
          </TouchableOpacity>
        </View>
      </Animated.View>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    width: MINI_PLAYER_WIDTH,
    height: MINI_PLAYER_HEIGHT,
    borderRadius: 12,
    overflow: 'hidden',
    backgroundColor: colors.neutral[900],
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.4,
    shadowRadius: 8,
    elevation: 12,
    zIndex: 9999,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  videoPreview: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.neutral[900],
    padding: 8,
  },
  liveBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginBottom: 4,
  },
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: '#EF4444',
  },
  liveText: {
    color: '#EF4444',
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  sessionTitle: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: '500',
    textAlign: 'center',
  },
  controls: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 6,
    paddingHorizontal: 8,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
  },
  miniButton: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  miniButtonMuted: {
    backgroundColor: colors.destructive,
  },
  miniButtonClose: {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  miniButtonIcon: {
    fontSize: 12,
  },
});
