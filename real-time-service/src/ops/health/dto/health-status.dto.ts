import { IsEnum, IsNotEmpty, IsString } from 'class-validator';

enum ServiceStatus {
  OPERATIONAL = 'OPERATIONAL',
  DEGRADED = 'DEGRADED',
  DOWNTIME = 'DOWNTIME',
  MAINTENANCE = 'MAINTENANCE',
}

export class HealthStatusDto {
  @IsString()
  @IsNotEmpty()
  service: string; // e.g., 'User & Org Service', 'Payment Gateway'

  @IsEnum(ServiceStatus)
  status: ServiceStatus;

  @IsString()
  @IsNotEmpty()
  message: string;
}
