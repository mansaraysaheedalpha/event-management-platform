import {
  IsEnum,
  IsNotEmpty,
  IsString,
  IsUUID,
  MaxLength,
} from 'class-validator';

// Match the enums defined in the Prisma schema
enum IncidentType {
  HARASSMENT = 'HARASSMENT',
  MEDICAL = 'MEDICAL',
  TECHNICAL = 'TECHNICAL',
  SECURITY = 'SECURITY',
  ACCESSIBILITY = 'ACCESSIBILITY',
}

enum IncidentSeverity {
  LOW = 'LOW',
  MEDIUM = 'MEDIUM',
  HIGH = 'HIGH',
  CRITICAL = 'CRITICAL',
}

export class ReportIncidentDto {
  @IsEnum(IncidentType)
  type: IncidentType;

  @IsEnum(IncidentSeverity)
  severity: IncidentSeverity;

  @IsString()
  @IsNotEmpty()
  @MaxLength(2000)
  details: string;

  @IsUUID(4)
  idempotencyKey: string;
}
