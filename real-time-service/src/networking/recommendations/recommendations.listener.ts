//src/networking/recommendations/recommendations.listener.ts
import { Injectable, Logger } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { RecommendationsService } from './recommendations.service';

/**
 * Event payload for check-in events
 */
interface CheckInEvent {
  userId: string;
  eventId: string;
  timestamp: string;
  metadata?: {
    registrationId?: string;
    ticketType?: string;
  };
}

/**
 * Event payload for session join events
 */
interface SessionJoinEvent {
  userId: string;
  eventId: string;
  sessionId: string;
  timestamp: string;
}

/**
 * RecommendationsListener handles event-driven triggers for recommendation generation.
 *
 * Triggers:
 * - Event check-in: Generate recommendations when user checks in to event
 * - Session join: Could trigger updates based on new session context
 *
 * These triggers help ensure recommendations are fresh and relevant when users
 * are actively engaging with an event.
 */
@Injectable()
export class RecommendationsListener {
  private readonly logger = new Logger(RecommendationsListener.name);

  constructor(private readonly recommendationsService: RecommendationsService) {}

  /**
   * Handle event check-in - trigger recommendation generation
   *
   * When a user checks in to an event:
   * 1. Generate personalized recommendations based on their profile
   * 2. Recommendations are cached and available in the "For You" tab
   */
  @OnEvent('platform.analytics.check-in.v1')
  async handleEventCheckIn(payload: CheckInEvent): Promise<void> {
    const { userId, eventId } = payload;

    this.logger.log(
      `Check-in event received for user ${userId} at event ${eventId}`,
    );

    try {
      // Trigger recommendation generation in the background
      // This doesn't block the check-in process
      await this.recommendationsService.triggerRecommendationGeneration(
        userId,
        eventId,
      );

      this.logger.log(
        `Recommendation generation triggered for user ${userId} at event ${eventId}`,
      );
    } catch (error) {
      // Log error but don't throw - recommendations are not critical for check-in
      this.logger.error(
        `Failed to trigger recommendations for user ${userId}: ${error}`,
      );
    }
  }

  /**
   * Handle session join - could enhance recommendations based on session interest
   *
   * Future enhancement: When a user joins a session, we could:
   * - Update their profile with inferred interests
   * - Adjust recommendation weights based on sessions attended
   */
  @OnEvent('session.user.joined')
  async handleSessionJoin(payload: SessionJoinEvent): Promise<void> {
    const { userId, eventId, sessionId } = payload;

    this.logger.debug(
      `Session join event: user ${userId} joined session ${sessionId} at event ${eventId}`,
    );

    // Future: Update user profile or re-rank recommendations based on session attendance
  }
}
