//src/alerts/incidents/dto/report-incident.dto.ts
import {
  IsEnum,
  IsNotEmpty,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

// Match the enums defined in the Prisma schema
export enum IncidentType {
  HARASSMENT = 'HARASSMENT',
  MEDICAL = 'MEDICAL',
  TECHNICAL = 'TECHNICAL',
  SECURITY = 'SECURITY',
  ACCESSIBILITY = 'ACCESSIBILITY',
}

export enum IncidentSeverity {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

/**
 * Payload submitted by users to report a new incident during a session.
 * Enforces classification by type and severity, plus full incident details.
 */
export class ReportIncidentDto {
  /** Type/category of the incident (e.g., HARASSMENT, TECHNICAL) */
  @IsEnum(IncidentType)
  type: IncidentType;

  /** Severity level of the incident (LOW to CRITICAL) */
  @IsEnum(IncidentSeverity)
  severity: IncidentSeverity;

  /** Detailed description of the incident (max 2000 chars) */
  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  details: string;

  /** Idempotency key to ensure duplicate reports aren’t stored */
  @IsUUID('4')
  idempotencyKey: string;
}
