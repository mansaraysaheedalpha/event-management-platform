// Main video player for attendees watching a live session
// Integrates DailyProvider, VideoGrid, VideoControls, and SubtitleOverlay

import React, { useEffect, useState, useCallback, useRef } from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native';
import { useQuery } from '@apollo/client/react';
import * as ScreenOrientation from 'expo-screen-orientation';
import { useDailyCall } from '@/providers/DailyProvider';
import { useVirtualStage } from '@/hooks/useVirtualStage';
import { useLiveSubtitles } from '@/hooks/useLiveSubtitles';
import { useSessionSocket } from '@/context/SessionSocketContext';
import { useAuthStore } from '@/store/auth.store';
import { GET_SESSION_BY_ID_QUERY } from '@/graphql/events.graphql';
import { VideoTile } from './VideoTile';
import { VideoGrid } from './VideoGrid';
import { VideoControls } from './VideoControls';
import { SubtitleOverlay } from './SubtitleOverlay';
import { colors } from '@/theme/colors';

interface SessionData {
  session: {
    id: string;
    title: string;
    streamingUrl: string | null;
    virtualRoomId: string | null;
    broadcastOnly: boolean;
    autoCaptions: boolean;
    streamingProvider: string | null;
    recordingUrl: string | null;
    speakers: { id: string; name: string; userId: string }[];
  };
}

interface SessionVideoPlayerProps {
  sessionId: string;
  eventId: string;
}

type ConnectionQuality = 'good' | 'fair' | 'poor' | 'unknown';

const MAX_JOIN_RETRIES = 20;
const RETRY_INTERVAL_MS = 3000;

export function SessionVideoPlayer({ sessionId, eventId }: SessionVideoPlayerProps) {
  const {
    participants,
    isJoined,
    isJoining,
    isCameraOn,
    isMicOn,
    captions,
    cpuLoadState,
    error: dailyError,
    joinCall,
    leaveCall,
    toggleCamera,
    toggleMic,
    setReceiveVideoQuality,
  } = useDailyCall();

  const { getToken, isLoading: tokenLoading, error: tokenError } = useVirtualStage();
  const { socket } = useSessionSocket();

  const { subtitles, enabled: subtitlesEnabled, toggleEnabled: toggleSubtitles } = useLiveSubtitles({
    socket,
    sessionId,
    autoTranslate: true,
  });

  const [connectionQuality, setConnectionQuality] = useState<ConnectionQuality>('unknown');
  const [joinError, setJoinError] = useState<string | null>(null);
  const [retryCount, setRetryCount] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [audioOnly, setAudioOnly] = useState(false);

  const retryTimerRef = useRef<NodeJS.Timeout | null>(null);
  const hasJoinedRef = useRef<boolean>(false);

  const user = useAuthStore((s) => s.user);

  // Fetch session details for video room info
  const { data: sessionData, loading: sessionLoading } = useQuery<SessionData>(GET_SESSION_BY_ID_QUERY, {
    variables: { id: sessionId },
  });

  const session = sessionData?.session;
  const roomName = session?.virtualRoomId || `stage-${sessionId}`;
  const streamingUrl = session?.streamingUrl;
  const broadcastOnly = session?.broadcastOnly ?? true;
  const autoCaptions = session?.autoCaptions ?? false;

  // Update connection quality based on CPU load
  useEffect(() => {
    if (cpuLoadState === 'critical') {
      setConnectionQuality('poor');
    } else if (cpuLoadState === 'high') {
      setConnectionQuality('fair');
    } else if (isJoined) {
      setConnectionQuality('good');
    }
  }, [cpuLoadState, isJoined]);

  // Auto-join the session video when room is available
  const attemptJoin = useCallback(async () => {
    if (hasJoinedRef.current || isJoined || isJoining) return;

    if (!streamingUrl) {
      // Room not created yet — retry with backoff
      if (retryCount < MAX_JOIN_RETRIES) {
        setJoinError('Waiting for the speaker to start the stream...');
        retryTimerRef.current = setTimeout(() => {
          setRetryCount((c) => c + 1);
        }, RETRY_INTERVAL_MS);
        return;
      }
      setJoinError('Stream is not available yet. The speaker may not have started.');
      return;
    }

    try {
      setJoinError(null);

      // Get a meeting token
      const token = await getToken({
        sessionId,
        roomName,
        isSpeaker: false,
        broadcastOnly,
      });

      if (!token) {
        setJoinError('Failed to get access token. Please try again.');
        return;
      }

      const userName = user
        ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email || 'Attendee'
        : 'Attendee';

      hasJoinedRef.current = true;
      await joinCall(streamingUrl, token, userName);
    } catch (err) {
      hasJoinedRef.current = false;
      setJoinError(err instanceof Error ? err.message : 'Failed to join video stream');
    }
  }, [streamingUrl, isJoined, isJoining, retryCount, sessionId, roomName, broadcastOnly, getToken, joinCall, user]);

  // Trigger join attempt when session data loads or retry count changes
  useEffect(() => {
    if (session && !isJoined && !hasJoinedRef.current) {
      attemptJoin();
    }
  }, [session, retryCount, attemptJoin, isJoined]);

  // Fullscreen orientation support
  useEffect(() => {
    const lock = isFullscreen
      ? ScreenOrientation.OrientationLock.LANDSCAPE
      : ScreenOrientation.OrientationLock.PORTRAIT_UP;
    ScreenOrientation.lockAsync(lock).catch(console.error);

    return () => {
      ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT_UP).catch(console.error);
    };
  }, [isFullscreen]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }
    };
  }, []);

  const handleRetry = useCallback(() => {
    hasJoinedRef.current = false;
    setRetryCount(0);
    setJoinError(null);
    attemptJoin();
  }, [attemptJoin]);

  const handleToggleFullscreen = useCallback(() => {
    setIsFullscreen((prev) => !prev);
  }, []);

  const handleToggleAudioOnly = useCallback(() => {
    setAudioOnly((prev) => {
      const newValue = !prev;
      if (newValue) {
        setReceiveVideoQuality('low');
      } else {
        setReceiveVideoQuality('medium');
      }
      return newValue;
    });
  }, [setReceiveVideoQuality]);

  // Loading state
  if (sessionLoading) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.primary.gold} />
        <Text style={styles.loadingText}>Loading session...</Text>
      </View>
    );
  }

  // Error state
  if (dailyError || tokenError || (joinError && retryCount >= MAX_JOIN_RETRIES)) {
    const errorMsg = dailyError || tokenError || joinError;
    return (
      <View style={styles.centerContainer}>
        <Text style={styles.errorIcon}>⚠️</Text>
        <Text style={styles.errorTitle}>Connection Error</Text>
        <Text style={styles.errorMessage}>{errorMsg}</Text>
        <TouchableOpacity style={styles.retryButton} onPress={handleRetry}>
          <Text style={styles.retryButtonText}>Try Again</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // Joining / waiting for stream
  if (!isJoined) {
    return (
      <View style={styles.centerContainer}>
        <ActivityIndicator size="large" color={colors.primary.gold} />
        <Text style={styles.loadingText}>
          {isJoining ? 'Connecting to video...' : joinError || 'Preparing video...'}
        </Text>
        {retryCount > 0 && retryCount < MAX_JOIN_RETRIES && (
          <Text style={styles.retryText}>
            Retry {retryCount}/{MAX_JOIN_RETRIES}
          </Text>
        )}
      </View>
    );
  }

  // Remote participants only (exclude local if broadcast-only attendee)
  const remoteParticipants = participants.filter((p) => !p.local);
  const allVisibleParticipants = broadcastOnly ? remoteParticipants : participants;

  return (
    <View style={[styles.container, isFullscreen && styles.containerFullscreen]}>
      {/* Connection quality indicator */}
      <View style={styles.qualityIndicator}>
        <View
          style={[
            styles.qualityDot,
            connectionQuality === 'good' && styles.qualityGood,
            connectionQuality === 'fair' && styles.qualityFair,
            connectionQuality === 'poor' && styles.qualityPoor,
          ]}
        />
        {audioOnly && (
          <View style={styles.audioOnlyBadge}>
            <Text style={styles.audioOnlyText}>Audio Only</Text>
          </View>
        )}
      </View>

      {/* Video content */}
      <View style={styles.videoContainer}>
        {allVisibleParticipants.length === 0 ? (
          <View style={styles.centerContainer}>
            <Text style={styles.noParticipants}>Waiting for speakers to join...</Text>
          </View>
        ) : allVisibleParticipants.length === 1 ? (
          <VideoTile
            participant={allVisibleParticipants[0]}
            isLocal={allVisibleParticipants[0].local}
            isLarge
            style={styles.singleVideo}
          />
        ) : (
          <VideoGrid participants={allVisibleParticipants} style={styles.videoGrid} />
        )}
      </View>

      {/* Subtitle overlay */}
      <SubtitleOverlay subtitles={subtitles} />

      {/* Fullscreen & audio-only toggles */}
      <View style={styles.topControls}>
        <TouchableOpacity
          style={styles.topControlButton}
          onPress={handleToggleAudioOnly}
          activeOpacity={0.7}
        >
          <Text style={styles.topControlIcon}>{audioOnly ? '🔊' : '🎬'}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.topControlButton}
          onPress={handleToggleFullscreen}
          activeOpacity={0.7}
        >
          <Text style={styles.topControlIcon}>{isFullscreen ? '⊟' : '⊞'}</Text>
        </TouchableOpacity>
      </View>

      {/* Video controls */}
      <VideoControls
        isMicOn={isMicOn}
        isCameraOn={isCameraOn}
        subtitlesEnabled={subtitlesEnabled}
        onToggleMic={toggleMic}
        onToggleCamera={toggleCamera}
        onToggleSubtitles={toggleSubtitles}
        onLeaveCall={leaveCall}
        onQualityChange={setReceiveVideoQuality}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  containerFullscreen: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    zIndex: 1000,
  },
  centerContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: colors.neutral[900],
    padding: 32,
  },
  loadingText: {
    color: '#FFFFFF',
    fontSize: 14,
    marginTop: 16,
    textAlign: 'center',
  },
  retryText: {
    color: colors.neutral[400],
    fontSize: 12,
    marginTop: 8,
  },
  errorIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  errorTitle: {
    color: '#FFFFFF',
    fontSize: 18,
    fontWeight: '600',
    marginBottom: 8,
  },
  errorMessage: {
    color: colors.neutral[400],
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 20,
  },
  retryButton: {
    backgroundColor: colors.primary.gold,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  retryButtonText: {
    color: colors.primary.navy,
    fontSize: 16,
    fontWeight: '600',
  },
  videoContainer: {
    flex: 1,
  },
  singleVideo: {
    width: '100%',
    height: '100%',
    borderRadius: 0,
    aspectRatio: undefined,
  },
  videoGrid: {
    flex: 1,
  },
  noParticipants: {
    color: colors.neutral[400],
    fontSize: 16,
    textAlign: 'center',
  },
  qualityIndicator: {
    position: 'absolute',
    top: 12,
    right: 12,
    zIndex: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  qualityDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.neutral[500],
  },
  qualityGood: {
    backgroundColor: colors.success,
  },
  qualityFair: {
    backgroundColor: colors.warning,
  },
  qualityPoor: {
    backgroundColor: colors.destructive,
  },
  audioOnlyBadge: {
    backgroundColor: 'rgba(0, 0, 0, 0.7)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  audioOnlyText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '500',
  },
  topControls: {
    position: 'absolute',
    top: 12,
    left: 12,
    zIndex: 10,
    flexDirection: 'row',
    gap: 8,
  },
  topControlButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  topControlIcon: {
    fontSize: 18,
  },
});
