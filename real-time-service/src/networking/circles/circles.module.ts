//src/networking/circles/circles.module.ts
import { Module } from '@nestjs/common';
import { CirclesService } from './circles.service';

@Module({
  providers: [CirclesService],
  exports: [CirclesService],
})
export class CirclesModule {}
