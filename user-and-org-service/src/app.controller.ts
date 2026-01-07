import { Controller, Get } from '@nestjs/common';
import { SkipThrottle } from '@nestjs/throttler';
import { AppService } from './app.service';

@SkipThrottle()
@Controller('health')
export class AppController {
  constructor(private readonly appService: AppService) {}

  @Get()
  getHealth(): Record<string, any> {
    return this.appService.getHealth();
  }
}
