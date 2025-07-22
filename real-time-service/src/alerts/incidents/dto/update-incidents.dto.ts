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

export class UpdateIncidentDto {
  @IsUUID(4)
  incidentId: string;

  @IsEnum(IncidentUpdateStatus)
  status: IncidentUpdateStatus;

  @IsString()
  @MaxLength(2000)
  @IsOptional()
  resolutionNotes?: string;

  @IsUUID(4)
  idempotencyKey: string;
}
