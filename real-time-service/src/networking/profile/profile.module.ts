//src/networking/profile/profile.module.ts
import { Module } from '@nestjs/common';
import { ProfileController } from './profile.controller';
import { ProfileService } from './profile.service';
import { PrismaModule } from 'src/prisma.module';

/**
 * Profile Module
 *
 * Handles user networking profiles for AI-powered recommendations.
 * Collects goals, interests, skills, and social media links.
 *
 * Features:
 * - Profile creation/update via REST API
 * - Profile completeness scoring
 * - Event emission for profile enrichment
 */
@Module({
  imports: [PrismaModule],
  controllers: [ProfileController],
  providers: [ProfileService],
  exports: [ProfileService],
})
export class ProfileModule {}
