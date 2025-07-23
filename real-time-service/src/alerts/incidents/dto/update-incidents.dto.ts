import {
  IsEnum,
  IsOptional,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

// Match the enums defined in the Prisma schema
// We exclude 'REPORTED' as this is the initial state
enum IncidentUpdateStatus {
  ACKNOWLEDGED = 'ACKNOWLEDGED',
  INVESTIGATING = 'INVESTIGATING',
  RESOLVED = 'RESOLVED',
}

/**
 * Payload for updating the status and resolution notes of an existing incident.
 * Used by admins/moderators during incident handling.
 */
export class UpdateIncidentDto {
  /** UUID of the incident being updated */
  @IsUUID('4')
  incidentId: string;

  /** New status of the incident (ACKNOWLEDGED, INVESTIGATING, RESOLVED) */
  @IsEnum(IncidentUpdateStatus)
  status: IncidentUpdateStatus;

  /** Optional notes describing how the incident was resolved */
  @IsString()
  @MaxLength(2000)
  @IsOptional()
  resolutionNotes?: string;

  /** Idempotency key to prevent duplicate updates */
  @IsUUID('4')
  idempotencyKey: string;
}
