// Incident types for organizer dashboard
// Ported from ../globalconnect/src/types/incident.types.ts

export type IncidentType =
  | 'HARASSMENT'
  | 'MEDICAL'
  | 'TECHNICAL'
  | 'SECURITY'
  | 'ACCESSIBILITY';

export type IncidentSeverity = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type IncidentStatus =
  | 'REPORTED'
  | 'ACKNOWLEDGED'
  | 'INVESTIGATING'
  | 'RESOLVED';

export type IncidentUpdateStatus = 'ACKNOWLEDGED' | 'INVESTIGATING' | 'RESOLVED';

export interface IncidentReporter {
  firstName: string;
  lastName: string;
}

export interface IncidentAssignee {
  firstName: string;
  lastName: string;
}

export interface Incident {
  id: string;
  createdAt: string;
  updatedAt: string;
  type: IncidentType;
  severity: IncidentSeverity;
  status: IncidentStatus;
  details: string;
  reporterId: string;
  organizationId: string;
  eventId: string;
  sessionId: string;
  assigneeId: string | null;
  resolutionNotes: string | null;
  reporter: IncidentReporter;
  assignee?: IncidentAssignee | null;
}

export interface IncidentFilters {
  status?: IncidentStatus[];
  severity?: IncidentSeverity[];
  type?: IncidentType[];
  searchQuery?: string;
}

export interface UpdateIncidentPayload {
  incidentId: string;
  status: IncidentUpdateStatus;
  resolutionNotes?: string;
  idempotencyKey: string;
}

export interface UpdateIncidentResponse {
  success: boolean;
  incidentId?: string;
  error?: string;
}

export interface JoinIncidentsResponse {
  success: boolean;
  error?: string;
  incidents?: Incident[];
}

// Display helpers
export const INCIDENT_TYPE_LABELS: Record<IncidentType, string> = {
  HARASSMENT: 'Harassment',
  MEDICAL: 'Medical',
  TECHNICAL: 'Technical',
  SECURITY: 'Security',
  ACCESSIBILITY: 'Accessibility',
};

export const INCIDENT_SEVERITY_LABELS: Record<IncidentSeverity, string> = {
  LOW: 'Low',
  MEDIUM: 'Medium',
  HIGH: 'High',
  CRITICAL: 'Critical',
};

export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  REPORTED: 'Reported',
  ACKNOWLEDGED: 'Acknowledged',
  INVESTIGATING: 'Investigating',
  RESOLVED: 'Resolved',
};
