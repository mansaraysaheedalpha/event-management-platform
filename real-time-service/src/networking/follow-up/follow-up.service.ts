//src/networking/follow-up/follow-up.service.ts
import { Injectable, Logger, NotFoundException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { PrismaService } from 'src/prisma.service';
import { KafkaService } from 'src/shared/kafka/kafka.service';
import { ConnectionsService, ConnectionWithContext } from '../connections/connections.service';
import { FollowUpTone, FollowUpSuggestionResponse } from './dto';

/**
 * Sanitize user input to prevent XSS and injection attacks.
 * Escapes HTML entities and removes potentially dangerous patterns.
 */
function sanitizeMessage(input: string): string {
  if (!input || typeof input !== 'string') {
    return '';
  }

  // Escape HTML entities
  let sanitized = input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');

  // Remove potential script injection patterns
  sanitized = sanitized.replace(/javascript:/gi, '');
  sanitized = sanitized.replace(/on\w+\s*=/gi, '');

  // Limit consecutive whitespace
  sanitized = sanitized.replace(/\s{10,}/g, '          ');

  return sanitized.trim();
}

// Note: ConnectionActivityType enum - ensure `npx prisma generate` is run after schema changes
// These values must match the enum in prisma/schema.prisma
const ConnectionActivityType = {
  INITIAL_CONNECT: 'INITIAL_CONNECT',
  DM_SENT: 'DM_SENT',
  DM_RECEIVED: 'DM_RECEIVED',
  HUDDLE_TOGETHER: 'HUDDLE_TOGETHER',
  FOLLOW_UP_SENT: 'FOLLOW_UP_SENT',
  FOLLOW_UP_OPENED: 'FOLLOW_UP_OPENED',
  FOLLOW_UP_REPLIED: 'FOLLOW_UP_REPLIED',
  MEETING_SCHEDULED: 'MEETING_SCHEDULED',
  MEETING_HELD: 'MEETING_HELD',
  OUTCOME_REPORTED: 'OUTCOME_REPORTED',
  LINKEDIN_CONNECTED: 'LINKEDIN_CONNECTED',
} as const;

// Oracle AI Service integration
interface OracleFollowUpRequest {
  connectionId: string;
  userId: string;
  otherUserName: string;
  otherUserHeadline?: string;
  connectionType: string;
  contexts: Array<{ type: string; value: string }>;
  initialMessage?: string;
  activities: Array<{ type: string; createdAt: string }>;
  tone: string;
  additionalContext?: string;
}

interface OracleFollowUpResponse {
  suggestedSubject: string;
  suggestedMessage: string;
  talkingPoints: string[];
  contextUsed: string[];
}

// Kafka topic for follow-up emails
export const KAFKA_TOPICS = {
  FOLLOW_UP_EMAILS: 'networking.follow-up-emails.v1',
} as const;

// Event interface for Kafka
export interface FollowUpEmailEvent {
  type: 'CONNECTION_FOLLOW_UP';
  userId: string;
  userEmail: string;
  userName: string;
  eventId: string;
  eventName: string;
  connections: Array<{
    connectionId: string;
    otherUserName: string;
    otherUserEmail: string;
    otherUserCompany?: string;
    initialMessage?: string;
    suggestedMessage: string;
    profileUrl: string;
    connectionContexts: string[];
  }>;
  scheduledFor: string;
}

export interface FollowUpEmailContent {
  subject: string;
  recipientEmail: string;
  recipientName: string;
  eventName: string;
  connections: Array<{
    connectionId: string;
    name: string;
    company?: string;
    initialContext?: string;
    suggestedMessage: string;
    profileUrl: string;
  }>;
  oneClickActions: {
    sendAllFollowUps: boolean;
    exportToLinkedIn: boolean;
  };
}

export interface FollowUpStats {
  totalScheduled: number;
  totalSent: number;
  totalOpened: number;
  totalReplied: number;
  openRate: number;
  replyRate: number;
}

// Configuration for Oracle AI service calls
const ORACLE_SERVICE_CONFIG = {
  TIMEOUT_MS: 10000, // 10 second timeout
  MAX_RETRIES: 2,
  RETRY_DELAY_MS: 1000,
} as const;

@Injectable()
export class FollowUpService {
  private readonly logger = new Logger(FollowUpService.name);
  private readonly oracleServiceUrl: string;
  private readonly oracleApiKey: string;

  constructor(
    private readonly prisma: PrismaService,
    private readonly kafkaService: KafkaService,
    private readonly connectionsService: ConnectionsService,
    private readonly configService: ConfigService,
  ) {
    this.oracleServiceUrl = this.configService.get<string>(
      'ORACLE_AI_SERVICE_URL',
      'http://localhost:8002',
    );
    this.oracleApiKey = this.configService.get<string>(
      'ORACLE_AI_SERVICE_API_KEY',
      '',
    );
  }

  /**
   * Make a fetch request with timeout and retry logic.
   */
  private async fetchWithRetry(
    url: string,
    options: RequestInit,
    retries: number = ORACLE_SERVICE_CONFIG.MAX_RETRIES,
  ): Promise<Response> {
    const controller = new AbortController();
    const timeoutId = setTimeout(
      () => controller.abort(),
      ORACLE_SERVICE_CONFIG.TIMEOUT_MS,
    );

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response;
    } catch (error) {
      clearTimeout(timeoutId);

      if (retries > 0 && error instanceof Error && error.name !== 'AbortError') {
        this.logger.warn(
          `Oracle AI service call failed, retrying (${retries} left): ${error.message}`,
        );
        await new Promise((resolve) =>
          setTimeout(resolve, ORACLE_SERVICE_CONFIG.RETRY_DELAY_MS),
        );
        return this.fetchWithRetry(url, options, retries - 1);
      }

      throw error;
    }
  }

  /**
   * Generate AI-powered follow-up message suggestion by calling oracle-ai-service.
   */
  async generateAIFollowUpSuggestion(
    connectionId: string,
    userId: string,
    tone: FollowUpTone = FollowUpTone.PROFESSIONAL,
    additionalContext?: string,
  ): Promise<FollowUpSuggestionResponse> {
    // Get connection with activities
    const connection = await this.connectionsService.getConnectionWithActivities(connectionId);

    // Authorization: Verify user is part of this connection
    if (connection.userAId !== userId && connection.userBId !== userId) {
      this.logger.warn(
        `Unauthorized access attempt: User ${userId} tried to generate follow-up for connection ${connectionId}`,
      );
      throw new NotFoundException('Connection not found');
    }

    // Determine other user
    const otherUser =
      connection.userAId === userId ? connection.userB : connection.userA;

    // Build request for oracle service
    const request: OracleFollowUpRequest = {
      connectionId,
      userId,
      otherUserName: `${otherUser.firstName || ''} ${otherUser.lastName || ''}`.trim(),
      connectionType: connection.connectionType,
      contexts: connection.contexts.map((c) => ({
        type: c.contextType,
        value: c.contextValue,
      })),
      initialMessage: connection.initialMessage || undefined,
      activities: (connection.activities || []).slice(0, 20).map((a) => ({
        type: a.activityType,
        createdAt: a.createdAt.toISOString(),
      })),
      tone,
      additionalContext: additionalContext
        ? sanitizeMessage(additionalContext)
        : undefined,
    };

    try {
      // Build headers with authentication
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
      };
      if (this.oracleApiKey) {
        headers['X-API-Key'] = this.oracleApiKey;
      }

      // Call oracle-ai-service with retry logic
      const response = await this.fetchWithRetry(
        `${this.oracleServiceUrl}/api/v1/networking/follow-up/generate`,
        {
          method: 'POST',
          headers,
          body: JSON.stringify(request),
        },
      );

      if (!response.ok) {
        this.logger.warn(
          `Oracle AI service returned ${response.status}, falling back to template`,
        );
        return this.generateFallbackSuggestion(connection, userId, tone);
      }

      const result: OracleFollowUpResponse = await response.json();

      // Store suggestion in connection for later use
      await this.connectionsService.storeFollowUpSuggestion(
        connectionId,
        result.suggestedMessage,
      );

      return {
        connectionId,
        ...result,
      };
    } catch (error) {
      this.logger.error(
        `Failed to call oracle-ai-service: ${error instanceof Error ? error.message : 'Unknown error'}`,
      );
      // Fall back to template-based generation
      return this.generateFallbackSuggestion(connection, userId, tone);
    }
  }

  /**
   * Fallback template-based suggestion when AI service is unavailable.
   */
  private generateFallbackSuggestion(
    connection: ConnectionWithContext,
    forUserId: string,
    tone: FollowUpTone,
  ): FollowUpSuggestionResponse {
    const message = this.generateSuggestedMessage(connection, forUserId);
    const contextUsed = connection.contexts.map((c) => c.contextValue);

    // Adjust tone
    let adjustedMessage = message;
    if (tone === FollowUpTone.CASUAL) {
      adjustedMessage = adjustedMessage.replace('Would love to', "Let's");
      adjustedMessage = adjustedMessage.replace('I would be interested in', "I'd love to");
    } else if (tone === FollowUpTone.FRIENDLY) {
      adjustedMessage = adjustedMessage.replace('Hi', 'Hey');
    }

    return {
      connectionId: connection.id,
      suggestedSubject: `Great meeting you!`,
      suggestedMessage: adjustedMessage,
      talkingPoints: contextUsed.length > 0 ? contextUsed : ['Your shared experience at the event'],
      contextUsed,
    };
  }

  /**
   * Schedule follow-up emails for all connections at an event.
   * Groups connections by user - each user gets one email with all their connections.
   */
  async scheduleEventFollowUps(
    eventId: string,
    scheduledFor?: Date,
  ): Promise<{ scheduledCount: number; userCount: number }> {
    // Get all connections for the event
    const connections = await this.connectionsService.getEventConnections(eventId);

    if (connections.length === 0) {
      this.logger.log(`No connections found for event ${eventId}`);
      return { scheduledCount: 0, userCount: 0 };
    }

    // Group connections by user
    const connectionsByUser = this.groupConnectionsByUser(connections);

    // Default to 24 hours from now if not specified
    const sendTime = scheduledFor || new Date(Date.now() + 24 * 60 * 60 * 1000);

    let scheduledCount = 0;
    for (const [userId, userConnections] of connectionsByUser) {
      const user = this.getUserFromConnections(userId, userConnections);

      if (!user.email) {
        this.logger.warn(`User ${userId} has no email, skipping follow-up`);
        continue;
      }

      // Create Kafka event for email worker
      const event: FollowUpEmailEvent = {
        type: 'CONNECTION_FOLLOW_UP',
        userId,
        userEmail: user.email,
        userName: user.name,
        eventId,
        eventName: `Event ${eventId}`, // Would be fetched from event service in production
        connections: userConnections.map((conn) => {
          const otherUser = this.getOtherUser(userId, conn);
          return {
            connectionId: conn.id,
            otherUserName: otherUser.name,
            otherUserEmail: otherUser.email,
            initialMessage: conn.initialMessage || undefined,
            suggestedMessage: this.generateSuggestedMessage(conn, userId),
            profileUrl: `/profile/${otherUser.id}`,
            connectionContexts: conn.contexts.map((c) => c.contextValue),
          };
        }),
        scheduledFor: sendTime.toISOString(),
      };

      // Send to Kafka queue
      await this.kafkaService.sendEvent(
        KAFKA_TOPICS.FOLLOW_UP_EMAILS,
        userId,
        event as unknown as Record<string, unknown>,
      );

      scheduledCount += userConnections.length;
    }

    this.logger.log(
      `Scheduled ${scheduledCount} follow-ups for ${connectionsByUser.size} users for event ${eventId}`,
    );

    return {
      scheduledCount,
      userCount: connectionsByUser.size,
    };
  }

  /**
   * Generate personalized follow-up email content for a user.
   */
  async generateFollowUpEmail(
    userId: string,
    eventId: string,
  ): Promise<FollowUpEmailContent> {
    const connections = await this.connectionsService.getUserEventConnections(
      userId,
      eventId,
    );

    if (connections.length === 0) {
      throw new NotFoundException(`No connections found for user ${userId} at event ${eventId}`);
    }

    const user = this.getUserFromConnections(userId, connections);

    return {
      subject: `Your ${connections.length} connection${connections.length > 1 ? 's' : ''} from the event`,
      recipientEmail: user.email,
      recipientName: user.name,
      eventName: `Event ${eventId}`,
      connections: connections.map((conn) => {
        const otherUser = this.getOtherUser(userId, conn);
        return {
          connectionId: conn.id,
          name: otherUser.name,
          initialContext: conn.initialMessage || undefined,
          suggestedMessage: this.generateSuggestedMessage(conn, userId),
          profileUrl: `/profile/${otherUser.id}`,
        };
      }),
      oneClickActions: {
        sendAllFollowUps: true,
        exportToLinkedIn: true,
      },
    };
  }

  /**
   * Send a follow-up message for a specific connection.
   */
  async sendFollowUpMessage(
    connectionId: string,
    message: string,
    senderId: string,
  ): Promise<{ success: boolean }> {
    // Sanitize user input to prevent XSS/injection
    const sanitizedMessage = sanitizeMessage(message);

    const connection = await this.connectionsService.getConnectionWithContext(connectionId);

    // Determine recipient
    const recipientId = connection.userAId === senderId
      ? connection.userBId
      : connection.userAId;

    const recipient = connection.userAId === senderId
      ? connection.userB
      : connection.userA;

    // Send message via Kafka (would trigger email worker)
    await this.kafkaService.sendEvent(
      KAFKA_TOPICS.FOLLOW_UP_EMAILS,
      connectionId,
      {
        type: 'DIRECT_FOLLOW_UP',
        connectionId,
        senderId,
        recipientId,
        recipientEmail: recipient.email,
        recipientName: `${recipient.firstName || ''} ${recipient.lastName || ''}`.trim(),
        message: sanitizedMessage,
        sentAt: new Date().toISOString(),
      },
    );

    // Mark follow-up as sent
    await this.connectionsService.markFollowUpSent(connectionId);

    // Log activity for strength calculation
    await this.connectionsService.logActivity({
      connectionId,
      activityType: ConnectionActivityType.FOLLOW_UP_SENT,
      initiatorId: senderId,
      description: 'Follow-up email sent',
    });

    this.logger.log(`Follow-up message sent for connection ${connectionId}`);
    return { success: true };
  }

  /**
   * Track email open via pixel.
   */
  async trackOpen(connectionId: string): Promise<void> {
    await this.connectionsService.markFollowUpOpened(connectionId);

    // Log activity for strength calculation
    await this.connectionsService.logActivity({
      connectionId,
      activityType: ConnectionActivityType.FOLLOW_UP_OPENED,
      description: 'Follow-up email opened',
    });

    this.logger.log(`Follow-up opened for connection ${connectionId}`);
  }

  /**
   * Track action click from email.
   */
  async trackAction(connectionId: string, action: string): Promise<void> {
    this.logger.log(`Action "${action}" tracked for connection ${connectionId}`);

    // If action is a reply-related action, mark as replied
    if (action === 'reply' || action === 'send-message') {
      await this.connectionsService.markFollowUpReplied(connectionId);

      // Log activity for strength calculation
      await this.connectionsService.logActivity({
        connectionId,
        activityType: ConnectionActivityType.FOLLOW_UP_REPLIED,
        description: `User replied via ${action}`,
      });
    }
  }

  /**
   * Get follow-up statistics for an event.
   */
  async getEventFollowUpStats(eventId: string): Promise<FollowUpStats> {
    const connections = await this.prisma.connection.findMany({
      where: { eventId },
      select: {
        followUpSentAt: true,
        followUpOpenedAt: true,
        followUpRepliedAt: true,
      },
    });

    const totalScheduled = connections.length;
    const totalSent = connections.filter((c) => c.followUpSentAt).length;
    const totalOpened = connections.filter((c) => c.followUpOpenedAt).length;
    const totalReplied = connections.filter((c) => c.followUpRepliedAt).length;

    return {
      totalScheduled,
      totalSent,
      totalOpened,
      totalReplied,
      openRate: totalSent > 0 ? (totalOpened / totalSent) * 100 : 0,
      replyRate: totalSent > 0 ? (totalReplied / totalSent) * 100 : 0,
    };
  }

  /**
   * Get pending follow-ups for a user.
   */
  async getPendingFollowUps(userId: string): Promise<ConnectionWithContext[]> {
    const connections = await this.connectionsService.getUserConnections(userId);
    return connections.filter((conn) => !conn.followUpSentAt);
  }

  /**
   * Group connections by user ID.
   */
  private groupConnectionsByUser(
    connections: ConnectionWithContext[],
  ): Map<string, ConnectionWithContext[]> {
    const byUser = new Map<string, ConnectionWithContext[]>();

    for (const conn of connections) {
      // Add to userA's list
      if (!byUser.has(conn.userAId)) {
        byUser.set(conn.userAId, []);
      }
      byUser.get(conn.userAId)!.push(conn);

      // Add to userB's list
      if (!byUser.has(conn.userBId)) {
        byUser.set(conn.userBId, []);
      }
      byUser.get(conn.userBId)!.push(conn);
    }

    return byUser;
  }

  /**
   * Get user info from their connections.
   */
  private getUserFromConnections(
    userId: string,
    connections: ConnectionWithContext[],
  ): { id: string; name: string; email: string } {
    const conn = connections[0];
    const user = conn.userAId === userId ? conn.userA : conn.userB;
    return {
      id: user.id,
      name: `${user.firstName || ''} ${user.lastName || ''}`.trim() || 'Attendee',
      email: user.email,
    };
  }

  /**
   * Get the other user from a connection.
   */
  private getOtherUser(
    userId: string,
    connection: ConnectionWithContext,
  ): { id: string; name: string; email: string } {
    const otherUser = connection.userAId === userId ? connection.userB : connection.userA;
    return {
      id: otherUser.id,
      name: `${otherUser.firstName || ''} ${otherUser.lastName || ''}`.trim() || 'Attendee',
      email: otherUser.email,
    };
  }

  /**
   * Generate AI-powered suggested follow-up message based on connection context.
   */
  private generateSuggestedMessage(
    connection: ConnectionWithContext,
    forUserId: string,
  ): string {
    const otherUser = this.getOtherUser(forUserId, connection);
    const firstName = otherUser.name.split(' ')[0];
    const contexts = connection.contexts;

    // Find shared session context
    const sharedSession = contexts.find((c) => c.contextType === 'SHARED_SESSION');
    if (sharedSession) {
      return `Hi ${firstName}, great meeting you! I enjoyed the "${sharedSession.contextValue}" session too. Would love to continue our conversation about what we discussed.`;
    }

    // Find shared interest context
    const sharedInterest = contexts.find((c) => c.contextType === 'SHARED_INTEREST');
    if (sharedInterest) {
      return `Hi ${firstName}, it was great connecting! I noticed we're both interested in ${sharedInterest.contextValue}. Would love to exchange ideas sometime.`;
    }

    // Find Q&A interaction
    const qaInteraction = contexts.find((c) => c.contextType === 'QA_INTERACTION');
    if (qaInteraction) {
      return `Hi ${firstName}, I found your question about "${qaInteraction.contextValue}" really interesting! Would love to discuss it further.`;
    }

    // Find mutual connection
    const mutualConnection = contexts.find((c) => c.contextType === 'MUTUAL_CONNECTION');
    if (mutualConnection) {
      return `Hi ${firstName}, great meeting you! I see we both know ${mutualConnection.contextValue}. Small world! Let's stay in touch.`;
    }

    // Default message with initial context if available
    if (connection.initialMessage) {
      return `Hi ${firstName}, it was great connecting at the event. ${connection.initialMessage ? `You mentioned "${connection.initialMessage}" - ` : ''}I'd love to continue our conversation!`;
    }

    return `Hi ${firstName}, it was great meeting you at the event. I'd love to stay in touch and continue our conversation!`;
  }
}
