// Gamification system types — matches real-time-service DTOs

export enum PointReason {
  MESSAGE_SENT = 'MESSAGE_SENT',
  MESSAGE_REACTED = 'MESSAGE_REACTED',
  QUESTION_ASKED = 'QUESTION_ASKED',
  QUESTION_UPVOTED = 'QUESTION_UPVOTED',
  POLL_CREATED = 'POLL_CREATED',
  POLL_VOTED = 'POLL_VOTED',
  WAITLIST_JOINED = 'WAITLIST_JOINED',
  TEAM_CREATED = 'TEAM_CREATED',
  TEAM_JOINED = 'TEAM_JOINED',
  SESSION_JOINED = 'SESSION_JOINED',
}

export const POINT_VALUES: Record<PointReason, number> = {
  [PointReason.MESSAGE_SENT]: 1,
  [PointReason.MESSAGE_REACTED]: 2,
  [PointReason.QUESTION_ASKED]: 5,
  [PointReason.QUESTION_UPVOTED]: 2,
  [PointReason.POLL_CREATED]: 10,
  [PointReason.POLL_VOTED]: 1,
  [PointReason.WAITLIST_JOINED]: 3,
  [PointReason.TEAM_CREATED]: 5,
  [PointReason.TEAM_JOINED]: 3,
  [PointReason.SESSION_JOINED]: 2,
};

export const REASON_TEXT: Record<PointReason, string> = {
  [PointReason.MESSAGE_SENT]: 'Sent a message',
  [PointReason.MESSAGE_REACTED]: 'Reacted to a message',
  [PointReason.QUESTION_ASKED]: 'Asked a question',
  [PointReason.QUESTION_UPVOTED]: 'Upvoted a question',
  [PointReason.POLL_CREATED]: 'Created a poll',
  [PointReason.POLL_VOTED]: 'Voted in a poll',
  [PointReason.WAITLIST_JOINED]: 'Joined the waitlist',
  [PointReason.TEAM_CREATED]: 'Created a team',
  [PointReason.TEAM_JOINED]: 'Joined a team',
  [PointReason.SESSION_JOINED]: 'Joined a session',
};

export const REASON_EMOJI: Record<PointReason, string> = {
  [PointReason.MESSAGE_SENT]: '💬',
  [PointReason.MESSAGE_REACTED]: '👍',
  [PointReason.QUESTION_ASKED]: '❓',
  [PointReason.QUESTION_UPVOTED]: '⬆️',
  [PointReason.POLL_CREATED]: '📊',
  [PointReason.POLL_VOTED]: '✅',
  [PointReason.WAITLIST_JOINED]: '⏳',
  [PointReason.TEAM_CREATED]: '🚀',
  [PointReason.TEAM_JOINED]: '🤜',
  [PointReason.SESSION_JOINED]: '🧭',
};

export interface LeaderboardEntry {
  rank: number;
  user: {
    id: string;
    firstName: string;
    lastName: string;
  };
  score: number;
}

export interface TeamLeaderboardEntry {
  teamId: string;
  name: string;
  score: number;
  rank: number;
  memberCount: number;
}

export interface RecentPointEvent {
  id: string;
  reason: PointReason;
  points: number;
  basePoints?: number;
  streakMultiplier?: number;
  streakCount?: number;
  timestamp: number;
}

export interface Achievement {
  id?: string;
  userId?: string;
  badgeName: string;
  description: string;
  icon?: string;
  category?: string;
  unlockedAt?: string;
  createdAt?: string;
}

export interface AchievementProgress {
  key: string;
  badgeName: string;
  description: string;
  icon: string;
  category: string;
  isUnlocked: boolean;
  unlockedAt: string | null;
  current: number;
  target: number;
  percentage: number;
}

export interface StreakInfo {
  count: number;
  multiplier: number;
  active: boolean;
}

export interface UserStats {
  totalPoints: number;
  rank: number | null;
  achievementCount: number;
  totalAchievements: number;
  streak: StreakInfo;
}

// Team types
export interface TeamMember {
  userId: string;
  teamId?: string;
  user?: {
    id: string;
    firstName: string;
    lastName: string;
    imageUrl?: string;
  };
  joinedAt?: string;
}

export interface Team {
  id: string;
  name: string;
  createdAt?: string;
  creatorId: string;
  sessionId: string;
  creator?: {
    id: string;
    firstName: string;
    lastName: string;
  };
  members: TeamMember[];
  score?: number;
}

export interface CreateTeamResponse {
  success: boolean;
  team?: Team;
  error?: string;
}

export interface JoinLeaveResponse {
  success: boolean;
  teamId?: string;
  error?: string;
}

// Achievement categories for UI grouping
export const ACHIEVEMENT_CATEGORIES = [
  { key: 'Social Butterfly', icon: '💬', label: 'Social Butterfly' },
  { key: 'Curious Mind', icon: '❓', label: 'Curious Mind' },
  { key: 'Voice of the People', icon: '📊', label: 'Voice of the People' },
  { key: 'Team Player', icon: '👥', label: 'Team Player' },
  { key: 'Event Explorer', icon: '🧭', label: 'Event Explorer' },
  { key: 'Milestones', icon: '⭐', label: 'Milestones' },
] as const;
