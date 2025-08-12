//src/ops/health/dto/health-status.dto.ts
import { IsEnum, IsNotEmpty, IsString } from 'class-validator';

/**
 * Enum representing the possible statuses of a microservice.
 */
enum ServiceStatus {
  OPERATIONAL = 'OPERATIONAL', // Everything is working fine
  DEGRADED = 'DEGRADED', // Service is slow or partially broken
  DOWNTIME = 'DOWNTIME', // Completely down or unavailable
  MAINTENANCE = 'MAINTENANCE', // Intentionally under maintenance
}

/**
 * DTO used for representing the current health status of a system component.
 * Validated using class-validator decorators.
 *
 * @example
 * const healthPayload: HealthStatusDto = {
 *   service: 'User Service',
 *   status: ServiceStatus.DEGRADED,
 *   message: 'High latency on user creation endpoint.',
 * };
 */
export class HealthStatusDto {
  /**
   * The name of the service reporting its health.
   * Should be descriptive (e.g., 'Auth Service', 'Event Microservice').
   */
  @IsString()
  @IsNotEmpty()
  service: string;

  /**
   * The current status of the service.
   * Must be one of the predefined values in ServiceStatus enum.
   */
  @IsEnum(ServiceStatus)
  status: ServiceStatus;

  /**
   * A human-readable message explaining the current state.
   */
  @IsString()
  @IsNotEmpty()
  message: string;
}
