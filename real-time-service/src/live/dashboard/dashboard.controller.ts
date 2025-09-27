import { Controller, Logger } from '@nestjs/common';
import { EventPattern, Payload } from '@nestjs/microservices';
import { DashboardService } from './dashboard.service';

@Controller()
export class DashboardController {
  private readonly logger = new Logger(DashboardController.name);

  constructor(private readonly dashboardService: DashboardService) {}

  @EventPattern('platform.analytics.check-in.v1')
  async handleCheckInEvent(@Payload() data: any) {
    this.logger.log(
      `Received check-in event from Kafka: ${JSON.stringify(data)}`,
    );
    await this.dashboardService.handleAnalyticsEvent(data);
  }
}
