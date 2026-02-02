import { IsString } from 'class-validator';

export type AnomalyType =
  | 'ENGAGEMENT_DROP'
  | 'SUDDEN_SPIKE'
  | 'SENTIMENT_SHIFT'
  | 'PARTICIPATION_DECLINE';

export type InterventionType =
  | 'POLL'
  | 'CHAT_PROMPT'
  | 'NUDGE'
  | 'CONTENT_SUGGESTION';

export type Severity = 'CRITICAL' | 'WARNING' | 'INFO';

// Incoming from Redis agent:notifications:{event_id} channel
export interface AnomalyDetectedPayload {
  type: 'anomaly_detected';
  event_id: string;
  timestamp: string;
  session_id: string;
  anomaly_type: AnomalyType;
  severity: Severity;
  engagement_score: number;
}

export interface InterventionExecutedPayload {
  type: 'intervention_executed';
  event_id: string;
  timestamp: string;
  session_id: string;
  intervention_type: InterventionType;
  confidence: number;
  auto_approved: boolean;
}

export type AgentNotificationPayload =
  | AnomalyDetectedPayload
  | InterventionExecutedPayload;

// Response DTOs
export class AgentNotificationResponseDto {
  id: string;
  createdAt: Date;
  eventId: string;
  sessionId: string | null;
  type: 'ANOMALY_DETECTED' | 'INTERVENTION_EXECUTED';
  severity: Severity;
  data: Record<string, unknown>;
  isRead: boolean;
}

export class MarkAllAsReadDto {
  @IsString()
  eventId: string;
}
