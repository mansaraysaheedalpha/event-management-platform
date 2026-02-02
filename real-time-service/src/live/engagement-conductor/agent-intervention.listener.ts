// src/live/engagement-conductor/agent-intervention.listener.ts
import { Injectable, Logger, Inject } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { PollsService } from '../../comm/polls/polls.service';
import { ChatService } from '../../comm/chat/chat.service';
import { Redis } from 'ioredis';
import { REDIS_CLIENT } from '../../shared/redis.constants';
import { v4 as uuidv4 } from 'uuid';

/**
 * Agent Intervention Listener
 *
 * Listens to agent.interventions Redis channel and executes interventions
 * sent by the agent-service (Engagement Conductor AI).
 *
 * Supported intervention types:
 * - agent.intervention.poll: Creates a new poll in the session
 * - agent.intervention.chat: Sends a chat prompt/message to the session
 * - agent.intervention.notification: Sends notifications to organizers
 * - agent.intervention.gamification: Triggers gamification events
 *
 * After execution, publishes outcomes to agent.intervention-outcomes for
 * the agent-service to complete its feedback loop (Thompson Sampling update).
 */
@Injectable()
export class AgentInterventionListener {
  private readonly logger = new Logger(AgentInterventionListener.name);

  // System user ID for agent-generated content
  private readonly AGENT_SYSTEM_USER_ID =
    process.env.AGENT_SYSTEM_USER_ID || 'system-engagement-agent';
  private readonly AGENT_SYSTEM_EMAIL =
    process.env.AGENT_SYSTEM_EMAIL || 'engagement-agent@system.local';

  constructor(
    private readonly pollsService: PollsService,
    private readonly chatService: ChatService,
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
          outcome = await this.handlePollIntervention(payload);
          break;

        case 'agent.intervention.chat':
          outcome = await this.handleChatIntervention(payload);
          break;

        case 'agent.intervention.notification':
          outcome = await this.handleNotificationIntervention(payload);
          break;

        case 'agent.intervention.gamification':
          outcome = await this.handleGamificationIntervention(payload);
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
   */
  private async handlePollIntervention(
    payload: PollInterventionPayload,
  ): Promise<InterventionOutcome> {
    const { intervention_id, session_id, event_id, poll, metadata } = payload;

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
   * Handle chat intervention - sends a prompt/message to the session
   */
  private async handleChatIntervention(
    payload: ChatInterventionPayload,
  ): Promise<InterventionOutcome> {
    const { intervention_id, session_id, event_id, prompt } = payload;

    this.logger.log(
      `Sending AI chat prompt in session ${session_id?.slice(0, 8)}...`,
    );

    try {
      // Send the message using ChatService
      const message = await this.chatService.sendMessage(
        this.AGENT_SYSTEM_USER_ID,
        this.AGENT_SYSTEM_EMAIL,
        session_id,
        {
          text: prompt,
          idempotencyKey: `agent-chat-${intervention_id}`,
        },
        event_id,
      );

      this.logger.log(
        `AI chat message sent: ${message?.id} - "${prompt?.slice(0, 50)}..."`,
      );

      return {
        success: true,
        intervention_id,
        session_id,
        event_id,
        result: {
          message_id: message?.id,
          prompt_preview: prompt?.slice(0, 100),
        },
      };
    } catch (error) {
      this.logger.error(
        `Failed to send AI chat message: ${error instanceof Error ? error.message : String(error)}`,
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
   * Handle gamification intervention - triggers gamification events
   */
  private async handleGamificationIntervention(
    payload: GamificationInterventionPayload,
  ): Promise<InterventionOutcome> {
    const { intervention_id, session_id, event_id, gamification } = payload;

    this.logger.log(
      `Processing gamification intervention: ${gamification?.event_type} for session ${session_id?.slice(0, 8)}...`,
    );

    // Publish gamification event to sync-events for processing
    const gamificationPayload = {
      type: 'gamification_event',
      resource: 'GAMIFICATION',
      action: 'TRIGGERED',
      sessionId: session_id,
      eventId: event_id,
      payload: {
        event_type: gamification?.event_type,
        content: gamification?.content,
        intervention_id,
      },
    };

    await this.redis.publish('sync-events', JSON.stringify(gamificationPayload));

    this.logger.log(`Gamification event published`);

    return {
      success: true,
      intervention_id,
      session_id,
      event_id,
      result: {
        gamification_type: gamification?.event_type,
        triggered: true,
      },
    };
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

interface ChatInterventionPayload extends BaseInterventionPayload {
  type: 'agent.intervention.chat';
  prompt: string;
}

interface NotificationInterventionPayload extends BaseInterventionPayload {
  type: 'agent.intervention.notification';
  notification_type: string;
  target?: string;
  escalate: boolean;
}

interface GamificationInterventionPayload extends BaseInterventionPayload {
  type: 'agent.intervention.gamification';
  gamification: {
    event_type: string;
    content?: Record<string, unknown>;
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
