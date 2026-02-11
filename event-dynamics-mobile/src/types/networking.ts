// Domain types for networking, connections, DMs, proximity, and recommendations
// Ported from ../globalconnect/src/types/connection.ts and ../globalconnect/src/types/proximity.ts

// ─── Connection Types ───────────────────────────────────────────────────────

export type ConnectionType = 'PROXIMITY_PING' | 'DM_INITIATED' | 'SESSION_QA' | 'MANUAL_EXCHANGE';
export type ConnectionStrength = 'WEAK' | 'MODERATE' | 'STRONG';
export type OutcomeType = 'MEETING_HELD' | 'JOB_REFERRAL' | 'PARTNERSHIP' | 'SALE_DEAL' | 'MENTORSHIP' | 'OTHER';
export type FollowUpTone = 'professional' | 'friendly' | 'casual';
export type ContextType = 'SHARED_SESSION' | 'SHARED_INTEREST' | 'MUTUAL_CONNECTION' | 'QA_INTERACTION' | 'POLL_AGREEMENT' | 'PROXIMITY';

export type ConnectionActivityType =
  | 'CONNECTION_CREATED'
  | 'FOLLOW_UP_SENT'
  | 'FOLLOW_UP_OPENED'
  | 'FOLLOW_UP_REPLIED'
  | 'OUTCOME_REPORTED'
  | 'DM_SENT'
  | 'PROFILE_VIEWED'
  | 'LINKEDIN_CONNECTED'
  | 'MEETING_SCHEDULED'
  | 'NOTE_ADDED'
  | 'STRENGTH_CHANGED';

export interface ConnectionUser {
  id: string;
  firstName: string;
  lastName: string;
  email: string;
  avatarUrl?: string | null;
  linkedInUrl?: string | null;
  company?: string | null;
  role?: string | null;
}

export interface ConnectionContext {
  contextType: ContextType;
  contextValue: string;
}

export interface ConnectionActivity {
  type: ConnectionActivityType;
  timestamp: string;
  metadata?: Record<string, string>;
}

export interface Connection {
  id: string;
  eventId: string;
  userA: ConnectionUser;
  userB: ConnectionUser;
  connectionType: ConnectionType;
  strength: ConnectionStrength;
  initialMessage?: string | null;
  contexts: ConnectionContext[];
  activities: ConnectionActivity[];
  followUpSent: boolean;
  followUpSentAt?: string | null;
  outcomeReported: boolean;
  outcomeType?: OutcomeType | null;
  outcomeNotes?: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface StrengthDistribution {
  WEAK: number;
  MODERATE: number;
  STRONG: number;
}

export interface FollowUpSuggestion {
  message: string;
  talkingPoints: string[];
  tone: FollowUpTone;
}

export interface ReportOutcomeDto {
  outcomeType: OutcomeType;
  notes?: string;
  meetingDate?: string;
}

export interface EventNetworkingStats {
  totalConnections: number;
  totalFollowUpsSent: number;
  totalOutcomesReported: number;
  followUpRate: number;
  outcomeRate: number;
}

export interface UserNetworkingStats {
  totalConnections: number;
  totalEvents: number;
  followUpsSent: number;
  followUpRate: number;
  outcomesReported: number;
  outcomeRate: number;
}

// ─── Event Connection Types ─────────────────────────────────────────────────

export interface EventConnectedUser {
  id: string;
  name: string;
  role?: string | null;
  company?: string | null;
  avatarUrl?: string | null;
  linkedInUrl?: string | null;
}

export interface EventConnection {
  id: string;
  connectedUserId: string;
  connectedAt: string;
  matchScore: number;
  reasons: string[];
  user: EventConnectedUser;
}

// ─── Recommendation Types ───────────────────────────────────────────────────

export interface RecommendedUser {
  id: string;
  name: string;
  role?: string | null;
  company?: string | null;
  avatarUrl?: string | null;
  linkedInUrl?: string | null;
  industry?: string | null;
  goals?: string[];
}

export interface Recommendation {
  id: string;
  userId: string;
  recommendedUserId: string;
  matchScore: number;
  reasons: string[];
  conversationStarters: string[];
  potentialValue?: string | null;
  generatedAt: string;
  expiresAt: string;
  viewed: boolean;
  pinged: boolean;
  connected: boolean;
  user: RecommendedUser;
}

// ─── Direct Message Types ───────────────────────────────────────────────────

export type MessageStatus = 'sending' | 'sent' | 'delivered' | 'read' | 'failed';

export interface DirectMessage {
  id: string;
  text: string;
  timestamp: string;
  senderId: string;
  conversationId: string;
  isDelivered: boolean;
  isRead: boolean;
  isEdited?: boolean;
  editedAt?: string | null;
  status?: MessageStatus;
}

export interface DMUser {
  id: string;
  firstName: string;
  lastName: string;
  avatar?: string | null;
  isOnline?: boolean;
}

export interface Conversation {
  id: string;
  recipientId: string;
  recipient: DMUser;
  lastMessage?: DirectMessage | null;
  unreadCount: number;
  updatedAt: string;
}

// ─── Proximity Types ────────────────────────────────────────────────────────

export interface NearbyUser {
  id: string;
  name: string;
  avatarUrl?: string | null;
  distance?: number | null;
  sharedInterests?: string[];
  connectionContexts?: ConnectionContextItem[];
  matchScore?: number | null;
  alreadyConnected?: boolean;
}

export interface ConnectionContextItem {
  contextType: ContextType;
  contextValue: string;
}

export interface ProximityPing {
  fromUser: { id: string; name: string };
  message: string;
  receivedAt: string;
}

export interface LocationCoordinates {
  latitude: number;
  longitude: number;
}

export interface ProximityResponse {
  success: boolean;
  error?: string;
}

export type SimpleRosterUpdate = { nearbyUserIds: string[] };

export type AdvancedRosterUpdate = {
  nearbyUsers: Array<{
    user: { id: string; name: string; avatarUrl?: string | null };
    distance?: number | null;
    sharedInterests?: string[];
    connectionContexts?: ConnectionContextItem[];
    matchScore?: number | null;
    alreadyConnected?: boolean;
  }>;
};

export type RosterUpdate = SimpleRosterUpdate | AdvancedRosterUpdate;

export function isAdvancedRosterUpdate(update: RosterUpdate): update is AdvancedRosterUpdate {
  return 'nearbyUsers' in update;
}

// ─── Follow-Up Types ────────────────────────────────────────────────────────

export interface FollowUpEmailContent {
  subject: string;
  recipientEmail: string;
  recipientName: string;
  eventName: string;
  connections: Array<{
    connectionId: string;
    name: string;
    company?: string;
    suggestedMessage: string;
  }>;
}

export interface FollowUpStats {
  totalScheduled: number;
  totalSent: number;
  totalOpened: number;
  totalReplied: number;
  openRate: number;
  replyRate: number;
}

// ─── Utility Functions ──────────────────────────────────────────────────────

export function getOtherUser(connection: Connection, currentUserId: string): ConnectionUser {
  return connection.userA.id === currentUserId ? connection.userB : connection.userA;
}

export function formatUserName(user: { firstName: string; lastName: string }): string {
  return `${user.firstName} ${user.lastName}`;
}

export function getUserInitials(user: { firstName: string; lastName: string }): string {
  return `${user.firstName.charAt(0)}${user.lastName.charAt(0)}`.toUpperCase();
}

export function getStrengthLabel(strength: ConnectionStrength): string {
  switch (strength) {
    case 'STRONG': return 'Strong';
    case 'MODERATE': return 'Growing';
    case 'WEAK': return 'New';
  }
}

export function getConnectionTypeLabel(type: ConnectionType): string {
  switch (type) {
    case 'PROXIMITY_PING': return 'Met nearby';
    case 'DM_INITIATED': return 'Started conversation';
    case 'SESSION_QA': return 'Session Q&A';
    case 'MANUAL_EXCHANGE': return 'Connected manually';
  }
}

export function formatDistanceText(meters: number | null | undefined): string {
  if (meters == null) return 'Nearby';
  if (meters < 10) return 'Very close';
  if (meters < 100) return `${Math.round(meters)}m away`;
  return `${(meters / 1000).toFixed(1)}km away`;
}
