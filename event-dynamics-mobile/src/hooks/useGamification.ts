// Gamification hook — socket-based points, leaderboard, achievements, streaks
// Ported from ../globalconnect/src/hooks/use-gamification.ts

import { useState, useEffect, useCallback, useRef } from 'react';
import { useSessionSocket } from '@/context/SessionSocketContext';
import { useAuthStore } from '@/store/auth.store';
import * as Haptics from 'expo-haptics';
import type {
  LeaderboardEntry,
  TeamLeaderboardEntry,
  RecentPointEvent,
  Achievement,
  AchievementProgress,
  StreakInfo,
  UserStats,
  PointReason,
} from '@/types/gamification';
import { REASON_TEXT, REASON_EMOJI } from '@/types/gamification';

const POINT_EVENT_LIFETIME_MS = 5000;

let pointEventIdCounter = 0;

export function useGamification() {
  const { socket, isConnected, isJoined } = useSessionSocket();
  const user = useAuthStore((s) => s.user);

  // Leaderboard
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [teamLeaderboard, setTeamLeaderboard] = useState<TeamLeaderboardEntry[]>([]);
  const [isLoadingLeaderboard, setIsLoadingLeaderboard] = useState(false);

  // User state
  const [currentScore, setCurrentScore] = useState(0);
  const [currentRank, setCurrentRank] = useState<number | null>(null);

  // Achievements
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [achievementProgress, setAchievementProgress] = useState<AchievementProgress[]>([]);

  // Points & streaks
  const [recentPointEvents, setRecentPointEvents] = useState<RecentPointEvent[]>([]);
  const [streak, setStreak] = useState<StreakInfo>({ count: 0, multiplier: 1, active: false });
  const [userStats, setUserStats] = useState<UserStats | null>(null);

  // Error
  const [error, setError] = useState<string | null>(null);

  // Activity counts (persists across animation clears)
  const activityCountsRef = useRef<Record<string, number>>({});

  // Track pending point-event timeouts for cleanup on unmount
  const pointTimeoutsRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  // Derive current user from leaderboard
  useEffect(() => {
    if (!user?.id || leaderboard.length === 0) return;
    const entry = leaderboard.find((e) => e.user.id === user.id);
    if (entry) {
      setCurrentRank(entry.rank);
      setCurrentScore(entry.score);
    }
  }, [leaderboard, user?.id]);

  // Socket event listeners
  useEffect(() => {
    if (!socket) return;

    // Leaderboard data (response to request)
    const handleLeaderboardData = (data: {
      topEntries: LeaderboardEntry[];
      currentUser?: { rank: number | null; score: number } | null;
    }) => {
      setLeaderboard(data.topEntries || []);
      if (data.currentUser) {
        setCurrentRank(data.currentUser.rank);
        setCurrentScore(data.currentUser.score);
      }
      setIsLoadingLeaderboard(false);
    };

    // Leaderboard broadcast update
    const handleLeaderboardUpdated = (data: { topEntries: LeaderboardEntry[] }) => {
      setLeaderboard(data.topEntries || []);
    };

    // Team leaderboard broadcast
    const handleTeamLeaderboardUpdated = (data: { teamScores: TeamLeaderboardEntry[] }) => {
      setTeamLeaderboard(data.teamScores || []);
    };

    // Points awarded (private)
    const handlePointsAwarded = (data: {
      reason: PointReason;
      points: number;
      basePoints: number;
      streakMultiplier?: number;
      streakCount?: number;
      newTotalScore: number;
    }) => {
      setCurrentScore(data.newTotalScore);

      // Track activity counts
      activityCountsRef.current[data.reason] =
        (activityCountsRef.current[data.reason] || 0) + 1;

      // Create point event for animation
      const eventId = `pt_${++pointEventIdCounter}_${Date.now()}`;
      const pointEvent: RecentPointEvent = {
        id: eventId,
        reason: data.reason,
        points: data.points,
        basePoints: data.basePoints,
        streakMultiplier: data.streakMultiplier,
        streakCount: data.streakCount,
        timestamp: Date.now(),
      };
      setRecentPointEvents((prev) => [...prev, pointEvent]);

      // Haptic feedback
      Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

      // Auto-clear after lifetime (tracked for cleanup on unmount)
      const timerId = setTimeout(() => {
        pointTimeoutsRef.current.delete(eventId);
        setRecentPointEvents((prev) => prev.filter((e) => e.id !== eventId));
      }, POINT_EVENT_LIFETIME_MS);
      pointTimeoutsRef.current.set(eventId, timerId);
    };

    // Streak updated (private)
    const handleStreakUpdated = (data: StreakInfo) => {
      setStreak(data);
    };

    // Achievements data (response to request)
    const handleAchievementsData = (data: {
      achievements: Achievement[];
      progress: AchievementProgress[];
    }) => {
      setAchievements(data.achievements || []);
      setAchievementProgress(data.progress || []);
    };

    // Achievement unlocked (private)
    const handleAchievementUnlocked = (achievement: Achievement) => {
      setAchievements((prev) => [...prev, achievement]);
      // Haptic feedback for achievement
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
      // Refresh achievement progress
      socket.emit('achievements.request');
    };

    // User stats data (response to request)
    const handleUserStatsData = (data: UserStats) => {
      setUserStats(data);
      if (data.streak) setStreak(data.streak);
      if (data.totalPoints !== undefined) setCurrentScore(data.totalPoints);
      if (data.rank !== undefined) setCurrentRank(data.rank);
    };

    socket.on('leaderboard.data', handleLeaderboardData);
    socket.on('leaderboard.updated', handleLeaderboardUpdated);
    socket.on('team.leaderboard.updated', handleTeamLeaderboardUpdated);
    socket.on('gamification.points.awarded', handlePointsAwarded);
    socket.on('gamification.streak.updated', handleStreakUpdated);
    socket.on('achievements.data', handleAchievementsData);
    socket.on('achievement.unlocked', handleAchievementUnlocked);
    socket.on('user.stats.data', handleUserStatsData);

    return () => {
      socket.off('leaderboard.data', handleLeaderboardData);
      socket.off('leaderboard.updated', handleLeaderboardUpdated);
      socket.off('team.leaderboard.updated', handleTeamLeaderboardUpdated);
      socket.off('gamification.points.awarded', handlePointsAwarded);
      socket.off('gamification.streak.updated', handleStreakUpdated);
      socket.off('achievements.data', handleAchievementsData);
      socket.off('achievement.unlocked', handleAchievementUnlocked);
      socket.off('user.stats.data', handleUserStatsData);

      // Clear pending point-event timeouts to prevent setState on unmounted hook
      for (const timerId of pointTimeoutsRef.current.values()) {
        clearTimeout(timerId);
      }
      pointTimeoutsRef.current.clear();
    };
  }, [socket]);

  // Auto-request data when joined
  useEffect(() => {
    if (!socket || !isJoined) return;
    socket.emit('leaderboard.request');
    socket.emit('achievements.request');
    socket.emit('user.stats.request');
    setIsLoadingLeaderboard(true);
  }, [socket, isJoined]);

  const requestLeaderboard = useCallback(() => {
    if (!socket || !isJoined) return;
    setIsLoadingLeaderboard(true);
    socket.emit('leaderboard.request');
  }, [socket, isJoined]);

  const requestAchievements = useCallback(() => {
    if (!socket || !isJoined) return;
    socket.emit('achievements.request');
  }, [socket, isJoined]);

  const requestUserStats = useCallback(() => {
    if (!socket || !isJoined) return;
    socket.emit('user.stats.request');
  }, [socket, isJoined]);

  const clearRecentAchievements = useCallback((ids: string[]) => {
    setAchievements((prev) =>
      prev.filter((a) => !ids.includes(a.id || a.badgeName))
    );
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const getReasonText = useCallback(
    (reason: PointReason) => REASON_TEXT[reason] || reason,
    []
  );

  const getReasonEmoji = useCallback(
    (reason: PointReason) => REASON_EMOJI[reason] || '🎯',
    []
  );

  return {
    isConnected,
    isJoined,
    error,
    leaderboard,
    teamLeaderboard,
    currentScore,
    currentRank,
    currentUserId: user?.id,
    achievements,
    achievementProgress,
    recentPointEvents,
    streak,
    userStats,
    activityCounts: activityCountsRef.current,
    isLoadingLeaderboard,
    requestLeaderboard,
    requestAchievements,
    requestUserStats,
    clearRecentAchievements,
    clearError,
    getReasonText,
    getReasonEmoji,
  };
}
