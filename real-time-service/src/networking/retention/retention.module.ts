// src/networking/retention/retention.module.ts
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ScheduleModule } from '@nestjs/schedule';
import { RetentionService } from './retention.service';
import { RetentionController } from './retention.controller';
import { PrismaService } from 'src/prisma.service';
import { KafkaModule } from 'src/shared/kafka/kafka.module';
import { ConnectionsModule } from '../connections/connections.module';
import { FollowUpModule } from '../follow-up/follow-up.module';

@Module({
  imports: [
    ConfigModule,
    ScheduleModule.forRoot(),
    KafkaModule,
    ConnectionsModule,
    FollowUpModule,
  ],
  controllers: [RetentionController],
  providers: [RetentionService, PrismaService],
  exports: [RetentionService],
})
export class RetentionModule {}
