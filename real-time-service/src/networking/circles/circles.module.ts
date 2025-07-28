import { Module } from '@nestjs/common';
import { CirclesService } from './circles.service';
import { CirclesGateway } from './circles.gateway';

@Module({
  providers: [CirclesService, CirclesGateway],
  exports: [CirclesService],
})
export class CirclesModule {}
