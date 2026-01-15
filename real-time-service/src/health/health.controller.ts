// src/health/health.controller.ts
import { Controller, Get } from '@nestjs/common';
import { getAllBreakerStats } from 'src/common/utils/circuit-breaker';

/**
 * Health Controller
 *
 * Provides endpoints for health checks and monitoring.
 * No authentication required for basic health check.
 */
@Controller('health')
export class HealthController {
  /**
   * Basic health check endpoint.
   * Used by load balancers and container orchestration.
   */
  @Get()
  healthCheck(): { status: string; timestamp: string } {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
    };
  }

  /**
   * Circuit breaker status endpoint.
   * Returns current state of all circuit breakers.
   * Useful for monitoring and debugging external service issues.
   */
  @Get('circuit-breakers')
  getCircuitBreakerStatus(): {
    status: string;
    breakers: ReturnType<typeof getAllBreakerStats>;
  } {
    const stats = getAllBreakerStats();
    const hasOpenBreaker = stats.some((b) => b.state === 'open');

    return {
      status: hasOpenBreaker ? 'degraded' : 'healthy',
      breakers: stats,
    };
  }
}
