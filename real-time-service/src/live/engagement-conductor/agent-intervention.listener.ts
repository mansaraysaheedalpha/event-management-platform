// src/live/engagement-conductor/agent-intervention.listener.ts
import { Injectable, Logger, Inject } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { PollsService } from '../../comm/polls/polls.service';
import { ChallengesService } from '../../gamification/teams/challenges/challenges.service';
import { CHALLENGE_TEMPLATES } from '../../gamification/teams/challenges/challenge-templates';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '../../shared/redis.constants';
import { ChallengeType } from '@prisma/client';

/**
 * Agent Intervention Listener
 *
 * Listens to agent.interventions Redis channel and executes interventions
 * sent by the agent-service (Engagement Conductor AI).
 *
 * Supported intervention types:
 * - agent.intervention.poll: Creates a new poll in the session
 * - agent.intervention.broadcast: Sends a banner announcement to all session attendees
 * - agent.intervention.notification: Sends notifications to organizers
 * - agent.intervention.gamification: Creates and starts a real challenge
 *
 * All attendee-facing interventions (poll, broadcast, gamification) also emit
 * a banner event via Redis pub/sub for the engagement-stream.listener to
 * forward to all attendees in the session room.
 *
 * After execution, publishes outcomes to agent.intervention-outcomes for
 * the agent-service to complete its feedback loop (Thompson Sampling update).
 */

interface InterventionBanner {
  type: 'poll' | 'broadcast' | 'gamification';
  interventionId: string;
  sessionId: string;
  eventId: string;
  title: string;
  message: string;
  icon: string;
  action?: string;
  template?: string;
  timestamp: string;
}

@Injectable()
export class AgentInterventionListener {
  private readonly logger = new Logger(AgentInterventionListener.name);

  // System user ID for agent-generated content
  private readonly AGENT_SYSTEM_USER_ID =
    process.env.AGENT_SYSTEM_USER_ID || 'system-engagement-agent';

  constructor(
    private readonly pollsService: PollsService,
    private readonly challengesService: ChallengesService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Handle incoming agent interventions from Redis Pub/Sub
   */
  @OnEvent('agent.interventions')
  async handleAgentIntervention(payload: unknown) {
    // Type guard for the payload
    if (!this.isValidInterventionPayload(payload)) {
      this.logger.warn('Invalid intervention payload received', payload);
      return;
    }

    const { type, intervention_id, session_id, event_id } = payload;

    this.logger.log(
      `Received agent intervention: ${type} for session ${session_id?.slice(0, 8)}...`,
    );

    try {
      let outcome: InterventionOutcome;

      switch (type) {
        case 'agent.intervention.poll':
          outcome = await this.handlePollIntervention(
            payload as PollInterventionPayload,
          );
          break;

        case 'agent.intervention.broadcast':
          outcome = await this.handleBroadcastIntervention(
            payload as BroadcastInterventionPayload,
          );
          break;

        case 'agent.intervention.notification':
          outcome = await this.handleNotificationIntervention(
            payload as NotificationInterventionPayload,
          );
          break;

        case 'agent.intervention.gamification':
          outcome = await this.handleGamificationIntervention(
            payload as GamificationInterventionPayload,
          );
          break;

        default:
          this.logger.warn(`Unknown intervention type: ${type}`);
          outcome = {
            success: false,
            intervention_id,
            session_id,
            event_id,
            error: `Unknown intervention type: ${type}`,
          };
      }

      // Publish outcome for agent-service feedback loop
      await this.publishInterventionOutcome(outcome);
    } catch (error) {
      this.logger.error(
        `Failed to execute intervention ${intervention_id}: ${error instanceof Error ? error.message : String(error)}`,
      );

      // Publish failure outcome
      await this.publishInterventionOutcome({
        success: false,
        intervention_id,
        session_id,
        event_id,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    }
  }

  /**
   * Handle poll intervention - creates a new poll in the session
   * Also emits a banner so attendees see a prominent notification.
   */
  private async handlePollIntervention(
    payload: PollInterventionPayload,
  ): Promise<InterventionOutcome> {
    const { intervention_id, session_id, event_id, poll } = payload;

    this.logger.log(
      `Creating AI-generated poll in session ${session_id?.slice(0, 8)}...`,
    );

    try {
      // Create the poll using PollsService
      const createdPoll = await this.pollsService.createPoll(
        this.AGENT_SYSTEM_USER_ID,
        session_id,
        {
          question: poll.question,
          options: poll.options.map((opt: string) => ({ text: opt })),
          idempotencyKey: `agent-poll-${intervention_id}`,
        },
        true, // skipEventRegistrationCheck - agent is a system user
      );

      this.logger.log(
        `AI poll created: ${createdPoll?.id} - "${poll.question?.slice(0, 50)}..."`,
      );

      // Emit banner to all attendees
      await this.emitInterventionBanner({
        type: 'poll',
        interventionId: intervention_id,
        sessionId: session_id,
        eventId: event_id,
        title: 'New Poll!',
        message: poll.question,
        icon: 'chart',
        timestamp: new Date().toISOString(),
      });

      return {
        success: true,
        intervention_id,
        session_id,
        event_id,
        result: {
          poll_id: createdPoll?.id,
          question: poll.question,
          options_count: poll.options?.length || 0,
        },
      };
    } catch (error) {
      this.logger.error(
        `Failed to create AI poll: ${error instanceof Error ? error.message : String(error)}`,
      );
      throw error;
    }
  }

  /**
   * Handle broadcast intervention - sends a prominent banner announcement
   * to all attendees in the session.
   */
  private async handleBroadcastIntervention(
    payload: BroadcastInterventionPayload,
  ): Promise<InterventionOutcome> {
    const { intervention_id, session_id, event_id, message } = payload;

    this.logger.log(
      `Broadcasting announcement in session ${session_id?.slice(0, 8)}...`,
    );

    try {
      // Emit banner to all attendees
      await this.emitInterventionBanner({
        type: 'broadcast',
        interventionId: intervention_id,
        sessionId: session_id,
        eventId: event_id,
        title: 'Announcement',
        message,
        icon: 'megaphone',
        timestamp: new Date().toISOString(),
      });

      this.logger.log(
        `Broadcast sent: "${message?.slice(0, 50)}..."`,
      );

      return {
        success: true,
        intervention_id,
        session_id,
        event_id,
        result: {
          message_preview: message?.slice(0, 100),
          delivered: true,
        },
      };
    } catch (error) {
      this.logger.error(
        `Failed to send broadcast: ${error instanceof Error ? error.message : String(error)}`,
      );
      throw error;
    }
  }

  /**
   * Handle notification intervention - logs and broadcasts to organizers
   */
  private async handleNotificationIntervention(
    payload: NotificationInterventionPayload,
  ): Promise<InterventionOutcome> {
    const {
      intervention_id,
      session_id,
      event_id,
      notification_type,
      target,
      escalate,
    } = payload;

    this.logger.log(
      `Processing notification intervention: ${notification_type} for event ${event_id?.slice(0, 8)}...`,
    );

    // Publish to agent notifications channel for organizer dashboard
    const notificationPayload = {
      type: 'agent_intervention',
      event_id,
      session_id,
      notification_type,
      target,
      escalate,
      timestamp: new Date().toISOString(),
      intervention_id,
    };

    await this.redis.publish(
      `agent:notifications:${event_id}`,
      JSON.stringify(notificationPayload),
    );

    this.logger.log(`Notification published to organizer dashboard`);

    return {
      success: true,
      intervention_id,
      session_id,
      event_id,
      result: {
        notification_type,
        delivered: true,
      },
    };
  }

  /**
   * Handle gamification intervention - creates and starts a real challenge,
   * then emits a banner so attendees see the challenge announcement.
   */
  private async handleGamificationIntervention(
    payload: GamificationInterventionPayload,
  ): Promise<InterventionOutcome> {
    const { intervention_id, session_id, event_id, content } = payload;

    this.logger.log(
      `Processing gamification intervention: ${content.action} for session ${session_id?.slice(0, 8)}...`,
    );

    try {
      if (content.action === 'START_CHALLENGE') {
        // Resolve the challenge type from the template key
        const templateKey = content.template || 'CHAT_BLITZ';
        const template = CHALLENGE_TEMPLATES[templateKey];

        if (!template) {
          throw new Error(`Unknown challenge template: ${templateKey}`);
        }

        // Create the challenge
        const challenge = await this.challengesService.createChallenge(
          this.AGENT_SYSTEM_USER_ID,
          session_id,
          {
            name: content.name || template.name,
            description: content.description || template.description,
            type: template.type as ChallengeType,
            durationMinutes: content.duration_minutes || template.durationMinutes,
            rewardFirst: content.rewards?.first ?? template.rewardFirst,
            rewardSecond: content.rewards?.second ?? template.rewardSecond,
            rewardThird: content.rewards?.third ?? template.rewardThird,
            idempotencyKey: `agent-challenge-${intervention_id}`,
          },
        );

        this.logger.log(
          `AI challenge created: ${challenge.id} (${challenge.name})`,
        );

        // Start the challenge immediately
        const startedChallenge = await this.challengesService.startChallenge(
          challenge.id,
        );

        this.logger.log(
          `AI challenge started: ${challenge.id} - ends at ${startedChallenge.endedAt}`,
        );

        // Emit banner to all attendees
        await this.emitInterventionBanner({
          type: 'gamification',
          interventionId: intervention_id,
          sessionId: session_id,
          eventId: event_id,
          title: content.name || 'Challenge Starting!',
          message: content.description || 'A new challenge has been launched!',
          action: content.action,
          template: content.template,
          icon: 'trophy',
          timestamp: new Date().toISOString(),
        });

        return {
          success: true,
          intervention_id,
          session_id,
          event_id,
          result: {
            challenge_id: challenge.id,
            challenge_name: challenge.name,
            challenge_type: challenge.type,
            duration_minutes: challenge.durationMinutes,
            started: true,
          },
        };
      }

      // For other gamification actions (e.g., POINTS_BOOST), emit banner only
      this.logger.log(
        `Gamification action ${content.action} - emitting banner`,
      );

      await this.emitInterventionBanner({
        type: 'gamification',
        interventionId: intervention_id,
        sessionId: session_id,
        eventId: event_id,
        title: content.name || 'Gamification Event!',
        message: content.description || 'Something exciting is happening!',
        action: content.action,
        template: content.template,
        icon: 'trophy',
        timestamp: new Date().toISOString(),
      });

      return {
        success: true,
        intervention_id,
        session_id,
        event_id,
        result: {
          action: content.action,
          triggered: true,
        },
      };
    } catch (error) {
      this.logger.error(
        `Failed to execute gamification intervention: ${error instanceof Error ? error.message : String(error)}`,
      );
      throw error;
    }
  }

  /**
   * Emit an intervention banner to all attendees in the session.
   * Publishes to Redis pub/sub channel for the engagement-stream.listener
   * to pick up and forward to WebSocket clients.
   */
  private async emitInterventionBanner(
    banner: InterventionBanner,
  ): Promise<void> {
    await this.redis.publish(
      'agent.intervention.banner',
      JSON.stringify(banner),
    );

    this.logger.log(
      `Intervention banner emitted: ${banner.type} for session ${banner.sessionId?.slice(0, 8)}...`,
    );
  }

  /**
   * Publish intervention outcome for agent-service feedback loop
   */
  private async publishInterventionOutcome(
    outcome: InterventionOutcome,
  ): Promise<void> {
    try {
      const outcomePayload = {
        ...outcome,
        timestamp: new Date().toISOString(),
      };

      // Publish to stream for agent-service to consume
      await this.redis.xadd(
        'platform.agent.intervention-outcomes.v1',
        '*',
        'data',
        JSON.stringify(outcomePayload),
      );

      // Also publish to pub/sub for immediate notification
      await this.redis.publish(
        'agent.intervention-outcomes',
        JSON.stringify(outcomePayload),
      );

      this.logger.log(
        `Intervention outcome published: ${outcome.intervention_id} - ${outcome.success ? 'SUCCESS' : 'FAILED'}`,
      );
    } catch (error) {
      this.logger.error(
        `Failed to publish intervention outcome: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }

  /**
   * Type guard for valid intervention payload
   */
  private isValidInterventionPayload(payload: unknown): payload is BaseInterventionPayload {
    if (typeof payload !== 'object' || payload === null) {
      return false;
    }

    const p = payload as Record<string, unknown>;
    return (
      typeof p.type === 'string' &&
      typeof p.intervention_id === 'string' &&
      typeof p.session_id === 'string'
    );
  }
}

// Type definitions for intervention payloads
interface BaseInterventionPayload {
  type: string;
  intervention_id: string;
  session_id: string;
  event_id: string;
  timestamp: string;
  metadata?: {
    reason?: string;
    confidence?: number;
    priority?: string;
    estimated_impact?: string;
  };
}

interface PollInterventionPayload extends BaseInterventionPayload {
  type: 'agent.intervention.poll';
  poll: {
    question: string;
    options: string[];
    type?: string;
    duration?: number;
  };
}

interface BroadcastInterventionPayload extends BaseInterventionPayload {
  type: 'agent.intervention.broadcast';
  message: string;
}

interface NotificationInterventionPayload extends BaseInterventionPayload {
  type: 'agent.intervention.notification';
  notification_type: string;
  target?: string;
  escalate: boolean;
}

interface GamificationInterventionPayload extends BaseInterventionPayload {
  type: 'agent.intervention.gamification';
  content: {
    action: 'START_CHALLENGE' | 'POINTS_BOOST';
    template?: 'CHAT_BLITZ' | 'POLL_RUSH' | 'QA_SPRINT' | 'POINTS_RACE';
    name: string;
    description: string;
    rewards?: { first: number; second: number; third: number };
    duration_minutes: number;
    multiplier?: number;
  };
}

interface InterventionOutcome {
  success: boolean;
  intervention_id: string;
  session_id: string;
  event_id: string;
  result?: Record<string, unknown>;
  error?: string;
}
