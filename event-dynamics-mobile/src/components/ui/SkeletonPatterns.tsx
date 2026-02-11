import React from 'react';
import { View, ScrollView, StyleSheet, Dimensions } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Skeleton } from './Skeleton';
import { colors, spacing } from '@/theme';

const { width: SCREEN_WIDTH } = Dimensions.get('window');

// Event registration card skeleton (AttendeeHomeScreen)
export function EventCardSkeleton() {
  return (
    <View style={skeletonStyles.eventCard}>
      <Skeleton width={80} height={80} borderRadius={8} />
      <View style={skeletonStyles.eventCardContent}>
        <Skeleton width={60} height={20} borderRadius={10} />
        <Skeleton width="70%" height={18} borderRadius={4} />
        <Skeleton width="50%" height={14} borderRadius={4} />
        <Skeleton width="30%" height={12} borderRadius={4} />
      </View>
    </View>
  );
}

// Large event browse card skeleton (EventBrowseScreen)
export function EventBrowseCardSkeleton() {
  const imageHeight = (SCREEN_WIDTH - 48) * 0.56;
  return (
    <View style={skeletonStyles.browseCard}>
      <Skeleton width="100%" height={imageHeight} borderRadius={12} />
      <View style={skeletonStyles.browseCardBody}>
        <Skeleton width="80%" height={20} borderRadius={4} />
        <Skeleton width="60%" height={14} borderRadius={4} />
        <Skeleton width="40%" height={12} borderRadius={4} />
      </View>
    </View>
  );
}

// Attendee row skeleton (AttendeeListScreen, ConnectionsListScreen)
export function AttendeeRowSkeleton() {
  return (
    <View style={skeletonStyles.attendeeRow}>
      <Skeleton width={44} height={44} borderRadius={22} />
      <View style={skeletonStyles.attendeeInfo}>
        <Skeleton width="60%" height={16} borderRadius={4} />
        <Skeleton width="40%" height={12} borderRadius={4} />
      </View>
    </View>
  );
}

// Leaderboard row skeleton
export function LeaderboardRowSkeleton() {
  return (
    <View style={skeletonStyles.leaderboardRow}>
      <Skeleton width={28} height={20} borderRadius={4} />
      <Skeleton width={40} height={40} borderRadius={20} />
      <View style={skeletonStyles.leaderboardInfo}>
        <Skeleton width="50%" height={16} borderRadius={4} />
        <Skeleton width="30%" height={12} borderRadius={4} />
      </View>
      <Skeleton width={48} height={20} borderRadius={4} />
    </View>
  );
}

// Chat message bubble skeleton
export function MessageBubbleSkeleton({ isOwn = false }: { isOwn?: boolean }) {
  return (
    <View
      style={[
        skeletonStyles.messageRow,
        isOwn && skeletonStyles.messageRowOwn,
      ]}
    >
      {!isOwn && <Skeleton width={32} height={32} borderRadius={16} />}
      <Skeleton
        width={isOwn ? 180 : 200}
        height={isOwn ? 48 : 60}
        borderRadius={16}
      />
    </View>
  );
}

// Session detail skeleton (hero + info)
export function SessionDetailSkeleton() {
  return (
    <View style={skeletonStyles.sessionDetail}>
      <Skeleton width="100%" height={200} borderRadius={0} />
      <View style={skeletonStyles.sessionDetailContent}>
        <Skeleton width="80%" height={24} borderRadius={4} />
        <Skeleton width="60%" height={16} borderRadius={4} />
        <Skeleton width="100%" height={14} borderRadius={4} />
        <Skeleton width="90%" height={14} borderRadius={4} />
        <View style={skeletonStyles.sessionDetailRow}>
          <Skeleton width={100} height={36} borderRadius={8} />
          <Skeleton width={100} height={36} borderRadius={8} />
        </View>
      </View>
    </View>
  );
}

// Notification row skeleton
export function NotificationRowSkeleton() {
  return (
    <View style={skeletonStyles.notificationRow}>
      <Skeleton width={40} height={40} borderRadius={20} />
      <View style={skeletonStyles.notificationInfo}>
        <Skeleton width="70%" height={14} borderRadius={4} />
        <Skeleton width="90%" height={12} borderRadius={4} />
        <Skeleton width="30%" height={10} borderRadius={4} />
      </View>
    </View>
  );
}

// Ticket card skeleton
export function TicketCardSkeleton() {
  return (
    <View style={skeletonStyles.ticketCard}>
      <Skeleton width="100%" height={80} borderRadius={8} />
      <View style={skeletonStyles.ticketCardContent}>
        <Skeleton width="70%" height={18} borderRadius={4} />
        <Skeleton width="50%" height={14} borderRadius={4} />
        <Skeleton width={120} height={120} borderRadius={8} style={{ alignSelf: 'center', marginTop: 12 }} />
      </View>
    </View>
  );
}

// Generic full-screen skeleton with repeating items
interface ScreenSkeletonProps {
  count?: number;
  ItemSkeleton?: React.ComponentType;
  header?: boolean;
}

export function ScreenSkeleton({
  count = 5,
  ItemSkeleton = EventCardSkeleton,
  header = true,
}: ScreenSkeletonProps) {
  return (
    <SafeAreaView style={skeletonStyles.screen} edges={['top']}>
      {header && (
        <View style={skeletonStyles.headerSkeleton}>
          <Skeleton width="50%" height={28} borderRadius={4} />
          <Skeleton width="30%" height={16} borderRadius={4} />
        </View>
      )}
      <ScrollView
        style={skeletonStyles.scrollView}
        contentContainerStyle={skeletonStyles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {Array.from({ length: count }, (_, i) => (
          <ItemSkeleton key={i} />
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const skeletonStyles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.background,
  },
  headerSkeleton: {
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 12,
    gap: 8,
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingHorizontal: 24,
    paddingBottom: 24,
  },
  eventCard: {
    flexDirection: 'row',
    gap: 12,
    padding: 12,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    marginBottom: 12,
    backgroundColor: colors.card,
  },
  eventCardContent: {
    flex: 1,
    gap: 6,
  },
  browseCard: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    marginBottom: 16,
    overflow: 'hidden',
    backgroundColor: colors.card,
  },
  browseCardBody: {
    padding: 16,
    gap: 8,
  },
  attendeeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
    marginBottom: 4,
  },
  attendeeInfo: {
    flex: 1,
    gap: 6,
  },
  leaderboardRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 8,
    paddingHorizontal: 4,
    marginBottom: 4,
  },
  leaderboardInfo: {
    flex: 1,
    gap: 4,
  },
  messageRow: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 8,
    marginBottom: 8,
  },
  messageRowOwn: {
    flexDirection: 'row-reverse',
  },
  sessionDetail: {
    flex: 1,
    backgroundColor: colors.background,
  },
  sessionDetailContent: {
    padding: 24,
    gap: 12,
  },
  sessionDetailRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
  },
  notificationRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 10,
    paddingHorizontal: 16,
    marginBottom: 4,
  },
  notificationInfo: {
    flex: 1,
    gap: 4,
  },
  ticketCard: {
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 12,
    marginBottom: 16,
    overflow: 'hidden',
    backgroundColor: colors.card,
  },
  ticketCardContent: {
    padding: 16,
    gap: 8,
  },
});
