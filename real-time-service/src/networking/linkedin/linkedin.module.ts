//src/networking/linkedin/linkedin.module.ts
import { Module } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { LinkedInService } from './linkedin.service';
import { LinkedInController } from './linkedin.controller';
import { PrismaService } from 'src/prisma.service';

@Module({
  imports: [ConfigModule],
  controllers: [LinkedInController],
  providers: [LinkedInService, PrismaService],
  exports: [LinkedInService],
})
export class LinkedInModule {}
