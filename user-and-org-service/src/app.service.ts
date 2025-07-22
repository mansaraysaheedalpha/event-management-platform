import { Injectable } from '@nestjs/common';

@Injectable()
export class AppService {
  getHealth(): Record<string, any> {
    return { status: 'ok', timestamp: new Date().toISOString() };
  }
}
