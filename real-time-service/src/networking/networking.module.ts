//src/networking/networking.module.ts
import { Module } from '@nestjs/common';
import { CirclesModule } from './circles/circles.module';
import { SuggestionsModule } from './suggestions/suggestions.module';
import { ProximityModule } from './proximity/proximity.module';
import { ConnectionsModule } from './connections/connections.module';
import { MatchingModule } from './matching/matching.module';
import { FollowUpModule } from './follow-up/follow-up.module';
import { NetworkingAnalyticsModule } from './analytics/analytics.module';
import { LinkedInModule } from './linkedin/linkedin.module';
import { HuddlesModule } from './huddles/huddles.module';
import { RecommendationsModule } from './recommendations/recommendations.module';
import { RetentionModule } from './retention/retention.module';
import { ProfileModule } from './profile/profile.module';
import { BreakoutModule } from './breakout/breakout.module';
import { ExpoModule } from '../expo/expo.module';

@Module({
  imports: [
    CirclesModule,
    SuggestionsModule,
    ProximityModule,
    ConnectionsModule,
    MatchingModule,
    FollowUpModule,
    NetworkingAnalyticsModule,
    LinkedInModule,
    HuddlesModule,
    RecommendationsModule,
    RetentionModule,
    ProfileModule,
    BreakoutModule,
    ExpoModule,
  ],
})
export class NetworkingModule {}
