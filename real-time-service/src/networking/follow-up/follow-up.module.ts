//src/networking/follow-up/follow-up.module.ts
import { Module, forwardRef } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { FollowUpService } from './follow-up.service';
import { FollowUpController } from './follow-up.controller';
import { PrismaService } from 'src/prisma.service';
import { SharedModule } from 'src/shared/shared.module';
import { KafkaModule } from 'src/shared/kafka/kafka.module';
import { ConnectionsModule } from '../connections/connections.module';

@Module({
  imports: [
    ConfigModule,
    SharedModule,
    KafkaModule,
    forwardRef(() => ConnectionsModule),
  ],
  controllers: [FollowUpController],
  providers: [FollowUpService, PrismaService],
  exports: [FollowUpService],
})
export class FollowUpModule {}
