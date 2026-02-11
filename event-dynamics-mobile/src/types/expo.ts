// Types for Expo Hall, Booths, Booth Chat — ported from web
// ../globalconnect/src/components/features/expo/types.ts

export type ExpoHallLayout = 'GRID' | 'FLOOR_PLAN' | 'LIST';
export type BoothTier = 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP';
export type BoothVisitorStatus = 'BROWSING' | 'IN_CHAT' | 'IN_VIDEO';
export type StaffPresenceStatus = 'ONLINE' | 'AWAY' | 'BUSY' | 'OFFLINE';

export interface ExpoHall {
  id: string;
  eventId: string;
  name: string;
  description: string | null;
  layout: ExpoHallLayout;
  categories: string[];
  opensAt: string | null;
  closesAt: string | null;
  isActive: boolean;
  bannerUrl: string | null;
  welcomeMessage: string | null;
  booths: ExpoBooth[];
}

export interface BoothResource {
  id: string;
  name: string;
  type: 'PDF' | 'VIDEO' | 'IMAGE' | 'DOCUMENT' | 'LINK' | 'OTHER';
  url: string;
  description?: string;
  thumbnailUrl?: string;
  downloadCount: number;
  fileSize?: number;
}

export interface BoothCta {
  id: string;
  label: string;
  url: string;
  style: 'primary' | 'secondary' | 'outline';
  icon?: string;
  order: number;
  clickCount: number;
}

export interface BoothStaffPresence {
  staffId: string;
  staffName: string;
  staffAvatarUrl: string | null;
  status: StaffPresenceStatus;
}

export interface ExpoBooth {
  id: string;
  expoHallId: string;
  sponsorId: string;
  boothNumber: string;
  tier: BoothTier;
  name: string;
  tagline: string | null;
  description: string | null;
  logoUrl: string | null;
  bannerUrl: string | null;
  videoUrl: string | null;
  resources: BoothResource[];
  ctaButtons: BoothCta[];
  staffIds: string[];
  chatEnabled: boolean;
  videoEnabled: boolean;
  category: string | null;
  displayOrder: number;
  staffPresence: BoothStaffPresence[];
  _count: {
    visits: number;
  };
}

export interface BoothVisit {
  id: string;
  boothId: string;
  userId: string;
  eventId: string;
  enteredAt: string;
  exitedAt: string | null;
  status: BoothVisitorStatus;
  durationSeconds: number;
  leadCaptured: boolean;
}

export interface BoothChatMessage {
  id: string;
  boothId: string;
  senderId: string;
  senderName: string;
  senderAvatarUrl: string | null;
  isStaff: boolean;
  text: string;
  createdAt: string;
  metadata?: Record<string, unknown>;
}

export interface BoothAnalytics {
  currentVisitors: number;
  totalVisitors: number;
  uniqueVisitors: number;
  peakVisitors: number;
  avgVisitDuration: number;
  totalChatMessages: number;
  totalVideoSessions: number;
  completedVideoSessions: number;
  avgVideoDuration: number;
  totalDownloads: number;
  totalCtaClicks: number;
  totalLeads: number;
  resourceDownloads: Record<string, number>;
  ctaClicks: Record<string, number>;
}

// Tier styling for React Native
export const BOOTH_TIER_COLORS: Record<BoothTier, { color: string; bg: string; border: string }> = {
  PLATINUM: { color: '#7C3AED', bg: '#F5F3FF', border: '#A78BFA' },
  GOLD: { color: '#D97706', bg: '#FFFBEB', border: '#FBBF24' },
  SILVER: { color: '#6B7280', bg: '#F9FAFB', border: '#9CA3AF' },
  BRONZE: { color: '#C2410C', bg: '#FFF7ED', border: '#FB923C' },
  STARTUP: { color: '#15803D', bg: '#F0FDF4', border: '#4ADE80' },
};
