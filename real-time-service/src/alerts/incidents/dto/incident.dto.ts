/**
 * Lightweight representation of the user who reported an incident.
 * Used for embedding basic reporter info in the incident response.
 */
class IncidentReporterDto {
  /** User ID of the reporter */
  id: string;

  /** First name of the reporter (nullable) */
  firstName: string | null;

  /** Last name of the reporter (nullable) */
  lastName: string | null;
}

/**
 * Full incident object returned to clients, enriched with reporter info.
 * Represents the complete lifecycle and state of a reported incident.
 */
export class IncidentDto {
  /** Unique incident ID */
  id: string;

  /** Timestamp when the incident was reported */
  createdAt: Date;

  /** Timestamp of the last update to the incident */
  updatedAt: Date;

  /** Type of incident (e.g., HARASSMENT, TECHNICAL) */
  type: string;

  /** Severity level (LOW to CRITICAL) */
  severity: string;

  /** Current status (e.g., REPORTED, ACKNOWLEDGED, RESOLVED) */
  status: string;

  /** Full incident description */
  details: string;

  /** ID of the user who reported it */
  reporterId: string;

  /** Org ID tied to the incident for multi-tenancy purposes */
  organizationId: string;

  /** Event ID linked to the session context */
  eventId: string;

  /** Session ID where the incident occurred */
  sessionId: string;

  /** Optional ID of the admin assigned to resolve this incident */
  assigneeId: string | null;

  /** Optional resolution notes written by an admin */
  resolutionNotes: string | null;

  /** Embedded user info of the person who reported the incident */
  reporter: IncidentReporterDto;
}
