// Breakout room screen with multi-participant video grid
// Ported from ../globalconnect/src/app/(attendee)/attendee/events/[eventId]/sessions/[sessionId]/breakout-rooms/[roomId]/page.tsx

import React, { useEffect, useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  FlatList,
  Modal,
  ActivityIndicator,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { RouteProp } from '@react-navigation/native';
import * as ScreenOrientation from 'expo-screen-orientation';
import { useDailyCall } from '@/providers/DailyProvider';
import { useVirtualStage } from '@/hooks/useVirtualStage';
import { useAuthStore } from '@/store/auth.store';
import { VideoGrid } from '@/components/video/VideoGrid';
import { VideoTile } from '@/components/video/VideoTile';
import { colors, typography } from '@/theme';
import type { HomeStackParamList } from '@/navigation/types';

type NavProp = NativeStackNavigationProp<HomeStackParamList, 'BreakoutRoom'>;
type RouteType = RouteProp<HomeStackParamList, 'BreakoutRoom'>;

export function BreakoutRoomScreen() {
  const navigation = useNavigation<NavProp>();
  const route = useRoute<RouteType>();
  const { eventId, sessionId, roomId } = route.params;

  const {
    participants,
    localParticipant,
    isJoined,
    isJoining,
    isCameraOn,
    isMicOn,
    cpuLoadState,
    error: dailyError,
    joinCall,
    leaveCall,
    toggleCamera,
    toggleMic,
    setReceiveVideoQuality,
  } = useDailyCall();

  const { getToken, isLoading: tokenLoading, error: tokenError } = useVirtualStage();
  const user = useAuthStore((s) => s.user);

  const [showParticipants, setShowParticipants] = useState(false);
  const [joinError, setJoinError] = useState<string | null>(null);
  const hasJoinedRef = useRef<boolean>(false);

  const roomName = `breakout-${roomId}`;
  const roomUrl = `https://eventdynamics.daily.co/${roomName}`;

  // Join the breakout room on mount
  useEffect(() => {
    if (hasJoinedRef.current || isJoined || isJoining) return;

    const join = async () => {
      try {
        const token = await getToken({
          sessionId,
          roomName,
          isSpeaker: true, // Breakout room participants can speak
          broadcastOnly: false,
        });

        if (!token) {
          setJoinError('Failed to get access token for breakout room');
          return;
        }

        const userName = user
          ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email || 'Participant'
          : 'Participant';

        hasJoinedRef.current = true;
        await joinCall(roomUrl, token, userName);
      } catch (err) {
        hasJoinedRef.current = false;
        setJoinError(err instanceof Error ? err.message : 'Failed to join breakout room');
      }
    };

    join();
  }, [sessionId, roomName, roomUrl, isJoined, isJoining, getToken, joinCall, user]);

  // Allow landscape orientation
  useEffect(() => {
    ScreenOrientation.unlockAsync().catch(console.error);
    return () => {
      ScreenOrientation.lockAsync(ScreenOrientation.OrientationLock.PORTRAIT_UP).catch(console.error);
    };
  }, []);

  const handleLeave = useCallback(() => {
    Alert.alert('Leave Breakout Room', 'Are you sure you want to leave this breakout room?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Leave',
        style: 'destructive',
        onPress: async () => {
          await leaveCall();
          navigation.goBack();
        },
      },
    ]);
  }, [leaveCall, navigation]);

  const handleRetry = useCallback(() => {
    hasJoinedRef.current = false;
    setJoinError(null);
  }, []);

  // Connection quality
  const qualityColor =
    cpuLoadState === 'critical' ? colors.destructive : cpuLoadState === 'high' ? colors.warning : colors.success;

  // Error state
  if (dailyError || tokenError || joinError) {
    const errorMsg = dailyError || tokenError || joinError;
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.errorContainer}>
          <Text style={styles.errorIcon}>⚠️</Text>
          <Text style={styles.errorTitle}>Connection Error</Text>
          <Text style={styles.errorMessage}>{errorMsg}</Text>
          <View style={styles.errorActions}>
            <TouchableOpacity style={styles.retryButton} onPress={handleRetry}>
              <Text style={styles.retryButtonText}>Try Again</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.backButton} onPress={() => navigation.goBack()}>
              <Text style={styles.backButtonText}>Go Back</Text>
            </TouchableOpacity>
          </View>
        </View>
      </SafeAreaView>
    );
  }

  // Loading state
  if (!isJoined) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color={colors.primary.gold} />
          <Text style={styles.loadingText}>
            {isJoining ? 'Joining breakout room...' : 'Preparing room...'}
          </Text>
        </View>
      </SafeAreaView>
    );
  }

  const remoteParticipants = participants.filter((p) => !p.local);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <View style={[styles.qualityDot, { backgroundColor: qualityColor }]} />
          <Text style={styles.headerTitle}>Breakout Room</Text>
        </View>
        <Text style={styles.participantCount}>
          {participants.length} participant{participants.length !== 1 ? 's' : ''}
        </Text>
      </View>

      {/* Video grid */}
      <View style={styles.videoArea}>
        {participants.length === 0 ? (
          <View style={styles.emptyContainer}>
            <Text style={styles.emptyText}>No participants yet</Text>
          </View>
        ) : participants.length === 1 && localParticipant ? (
          <View style={styles.soloContainer}>
            <VideoTile participant={localParticipant} isLocal isLarge style={styles.soloTile} />
            <Text style={styles.waitingText}>Waiting for others to join...</Text>
          </View>
        ) : (
          <VideoGrid participants={participants} style={styles.grid} />
        )}
      </View>

      {/* Self-view overlay (small corner PIP when grid has multiple participants) */}
      {localParticipant && participants.length > 2 && (
        <View style={styles.selfViewCorner}>
          <VideoTile participant={localParticipant} isLocal style={styles.selfViewTile} />
        </View>
      )}

      {/* Floating controls */}
      <View style={styles.floatingControls}>
        <TouchableOpacity
          style={[styles.controlButton, !isMicOn && styles.controlButtonMuted]}
          onPress={toggleMic}
          activeOpacity={0.7}
        >
          <Text style={styles.controlIcon}>{isMicOn ? '🎤' : '🔇'}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.controlButton, !isCameraOn && styles.controlButtonMuted]}
          onPress={toggleCamera}
          activeOpacity={0.7}
        >
          <Text style={styles.controlIcon}>{isCameraOn ? '📹' : '📵'}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.controlButton}
          onPress={() => setShowParticipants(true)}
          activeOpacity={0.7}
        >
          <Text style={styles.controlIcon}>👥</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.controlButton, styles.controlButtonLeave]}
          onPress={handleLeave}
          activeOpacity={0.7}
        >
          <Text style={styles.controlIcon}>❌</Text>
        </TouchableOpacity>
      </View>

      {/* Participant list modal */}
      <Modal
        visible={showParticipants}
        transparent
        animationType="slide"
        onRequestClose={() => setShowParticipants(false)}
      >
        <TouchableOpacity
          style={styles.modalOverlay}
          activeOpacity={1}
          onPress={() => setShowParticipants(false)}
        >
          <View style={styles.participantModal}>
            <View style={styles.modalHandle} />
            <Text style={styles.modalTitle}>
              Participants ({participants.length})
            </Text>

            <FlatList
              data={participants}
              keyExtractor={(item) => item.session_id}
              renderItem={({ item }) => (
                <View style={styles.participantRow}>
                  <View
                    style={[
                      styles.participantAvatar,
                      { backgroundColor: item.local ? colors.primary.gold : colors.info },
                    ]}
                  >
                    <Text style={styles.participantInitial}>
                      {(item.user_name || '?')[0]?.toUpperCase()}
                    </Text>
                  </View>
                  <View style={styles.participantInfo}>
                    <Text style={styles.participantName}>
                      {item.user_name || 'Participant'}
                      {item.local ? ' (You)' : ''}
                    </Text>
                  </View>
                  <View style={styles.participantStatus}>
                    <Text style={styles.statusIcon}>{item.audio ? '🎤' : '🔇'}</Text>
                    <Text style={styles.statusIcon}>{item.video ? '📹' : '📵'}</Text>
                  </View>
                </View>
              )}
              ItemSeparatorComponent={() => <View style={styles.separator} />}
            />

            <TouchableOpacity
              style={styles.closeModalButton}
              onPress={() => setShowParticipants(false)}
            >
              <Text style={styles.closeModalText}>Close</Text>
            </TouchableOpacity>
          </View>
        </TouchableOpacity>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#000000',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
  },
  headerLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  qualityDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  headerTitle: {
    ...typography.body,
    color: '#FFFFFF',
    fontWeight: '600',
  },
  participantCount: {
    ...typography.bodySmall,
    color: colors.neutral[400],
  },
  videoArea: {
    flex: 1,
  },
  grid: {
    flex: 1,
  },
  emptyContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    color: colors.neutral[400],
    fontSize: 16,
  },
  soloContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  soloTile: {
    width: '100%',
    maxHeight: 300,
  },
  waitingText: {
    color: colors.neutral[400],
    fontSize: 14,
    marginTop: 16,
  },
  selfViewCorner: {
    position: 'absolute',
    top: 60,
    right: 12,
    zIndex: 10,
  },
  selfViewTile: {
    width: 100,
    height: 75,
    borderRadius: 8,
    borderWidth: 2,
    borderColor: colors.primary.gold,
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#FFFFFF',
    fontSize: 14,
    marginTop: 16,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
    backgroundColor: colors.neutral[900],
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
  errorActions: {
    flexDirection: 'row',
    gap: 12,
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
  backButton: {
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderRadius: 8,
  },
  backButtonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '500',
  },
  floatingControls: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 16,
    paddingVertical: 16,
    paddingHorizontal: 24,
    backgroundColor: 'rgba(0, 0, 0, 0.8)',
  },
  controlButton: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  controlButtonMuted: {
    backgroundColor: colors.destructive,
  },
  controlButtonLeave: {
    backgroundColor: colors.destructive,
  },
  controlIcon: {
    fontSize: 24,
  },
  // Participant modal
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    justifyContent: 'flex-end',
  },
  participantModal: {
    backgroundColor: '#FFFFFF',
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    padding: 20,
    maxHeight: '60%',
  },
  modalHandle: {
    width: 40,
    height: 4,
    backgroundColor: colors.neutral[300],
    borderRadius: 2,
    alignSelf: 'center',
    marginBottom: 16,
  },
  modalTitle: {
    ...typography.h3,
    color: colors.primary.navy,
    marginBottom: 16,
  },
  participantRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
  },
  participantAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
  },
  participantInitial: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: '600',
  },
  participantInfo: {
    flex: 1,
    marginLeft: 12,
  },
  participantName: {
    ...typography.body,
    color: colors.primary.navy,
    fontWeight: '500',
  },
  participantStatus: {
    flexDirection: 'row',
    gap: 6,
  },
  statusIcon: {
    fontSize: 16,
  },
  separator: {
    height: 1,
    backgroundColor: colors.border,
  },
  closeModalButton: {
    marginTop: 16,
    paddingVertical: 14,
    borderRadius: 12,
    backgroundColor: colors.neutral[200],
    alignItems: 'center',
  },
  closeModalText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary.navy,
  },
});
