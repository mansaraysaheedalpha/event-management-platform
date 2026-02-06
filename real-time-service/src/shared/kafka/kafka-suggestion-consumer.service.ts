//src/shared/kafka/kafka-suggestion-consumer.service.ts
import {
  Injectable,
  OnModuleInit,
  OnModuleDestroy,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { Kafka, Consumer, logLevel, SASLOptions, EachMessagePayload } from 'kafkajs';
import { PrismaService } from 'src/prisma.service';

/**
 * Kafka topic for networking suggestions from Oracle AI service
 */
export const KAFKA_TOPIC_NETWORKING_SUGGESTIONS =
  'oracle.predictions.networking-suggestions';

/**
 * Incoming payload from Oracle AI service via Kafka
 * Matches NetworkingSuggestionPayload from oracle-ai-service/app/schemas/messaging.py
 */
export interface NetworkingSuggestionPayload {
  suggestionId: string;
  eventId: string;
  recipientUserId: string;
  suggestedUserId: string;
  matchScore: number;
  matchReasons: string[];
  suggestedIceBreaker: string;
  timestamp: string;
}

/**
 * Enriched payload emitted to internal event system
 * Matches AiSuggestionPayload expected by SuggestionsService
 */
export interface EnrichedConnectionSuggestion {
  type: 'CONNECTION_SUGGESTION';
  suggestionId: string;
  eventId: string;
  targetUserId: string;
  suggestedUserId: string;
  suggestedUserName: string;
  suggestedUserAvatar?: string;
  suggestedUserTitle?: string;
  suggestedUserCompany?: string;
  reason: string;
  matchScore: number;
  sharedInterests?: string[];
  conversationStarter?: string;
  timestamp: string;
}

/**
 * KafkaSuggestionConsumerService bridges Kafka → EventEmitter for AI suggestions.
 *
 * Flow:
 * 1. Oracle AI Service publishes NetworkingSuggestionPayload to Kafka topic
 * 2. This consumer receives the message
 * 3. Enriches with user data (name, avatar, title, company)
 * 4. Emits 'ai-suggestions' event via EventEmitter2
 * 5. SuggestionsService handles event and routes to WebSocket gateway
 *
 * This creates the bridge:
 * Oracle AI → Kafka → KafkaSuggestionConsumer → EventEmitter → SuggestionsGateway → WebSocket
 */
@Injectable()
export class KafkaSuggestionConsumerService
  implements OnModuleInit, OnModuleDestroy
{
  private readonly logger = new Logger(KafkaSuggestionConsumerService.name);
  private kafka: Kafka;
  private consumer: Consumer;
  private isConnected = false;

  constructor(
    private readonly configService: ConfigService,
    private readonly eventEmitter: EventEmitter2,
    private readonly prisma: PrismaService,
  ) {
    const brokers = this.configService
      .get<string>('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
      .split(',');
    const kafkaApiKey = this.configService.get<string>('KAFKA_API_KEY');
    const kafkaApiSecret = this.configService.get<string>('KAFKA_API_SECRET');

    // Build Kafka configuration with optional SASL authentication
    const kafkaConfig: ConstructorParameters<typeof Kafka>[0] = {
      clientId: 'real-time-service-suggestion-consumer',
      brokers,
      logLevel: logLevel.WARN,
      retry: {
        initialRetryTime: 300,
        retries: 5,
      },
    };

    // Add SASL/SSL authentication if credentials are provided (Confluent Cloud)
    if (kafkaApiKey && kafkaApiSecret) {
      kafkaConfig.ssl = true;
      kafkaConfig.sasl = {
        mechanism: 'plain',
        username: kafkaApiKey,
        password: kafkaApiSecret,
      } as SASLOptions;
      this.logger.log('Kafka consumer configured with SASL_SSL authentication');
    }

    this.kafka = new Kafka(kafkaConfig);
    this.consumer = this.kafka.consumer({
      groupId: 'real-time-service-suggestions-group',
    });
  }

  async onModuleInit() {
    try {
      await this.consumer.connect();
      this.isConnected = true;
      this.logger.log('Kafka suggestion consumer connected');

      // Subscribe to the networking suggestions topic
      await this.consumer.subscribe({
        topic: KAFKA_TOPIC_NETWORKING_SUGGESTIONS,
        fromBeginning: false,
      });

      // Start consuming messages
      await this.consumer.run({
        eachMessage: async (payload: EachMessagePayload) => {
          await this.handleMessage(payload);
        },
      });

      this.logger.log(
        `Subscribed to topic: ${KAFKA_TOPIC_NETWORKING_SUGGESTIONS}`,
      );
    } catch (error) {
      this.logger.error('Failed to connect Kafka suggestion consumer:', error);
      // Don't throw - allow service to start even if Kafka is unavailable
    }
  }

  async onModuleDestroy() {
    try {
      await this.consumer.disconnect();
      this.logger.log('Kafka suggestion consumer disconnected');
    } catch (error) {
      this.logger.error(
        'Error disconnecting Kafka suggestion consumer:',
        error,
      );
    }
  }

  /**
   * Handle incoming Kafka message
   */
  private async handleMessage({ message, topic }: EachMessagePayload) {
    if (!message.value) {
      this.logger.warn('Received empty message, skipping');
      return;
    }

    try {
      const payload: NetworkingSuggestionPayload = JSON.parse(
        message.value.toString(),
      );
      this.logger.log(
        `Received suggestion for user ${payload.recipientUserId}`,
      );

      // Enrich with user data and emit event
      const enrichedPayload = await this.enrichAndTransform(payload);
      this.eventEmitter.emit('ai-suggestions', enrichedPayload);

      this.logger.log(
        `Emitted suggestion for user ${payload.recipientUserId}: ${enrichedPayload.suggestedUserName}`,
      );
    } catch (error) {
      this.logger.error(`Failed to process message from ${topic}:`, error);
    }
  }

  /**
   * Transform Kafka payload to enriched suggestion format
   * Fetches user details from database
   */
  private async enrichAndTransform(
    payload: NetworkingSuggestionPayload,
  ): Promise<EnrichedConnectionSuggestion> {
    // Fetch user info for the suggested user
    const user = await this.prisma.userReference.findUnique({
      where: { id: payload.suggestedUserId },
      select: {
        id: true,
        firstName: true,
        lastName: true,
        avatarUrl: true,
      },
    });

    // Fetch profile for additional details
    const profile = await this.prisma.userProfile.findUnique({
      where: { userId: payload.suggestedUserId },
      select: {
        currentRole: true,
        company: true,
        interests: true,
      },
    });

    // Build user name
    const suggestedUserName = user
      ? `${user.firstName || ''} ${user.lastName || ''}`.trim() || 'Attendee'
      : 'Attendee';

    // Extract shared interests if available
    const sharedInterests = profile?.interests
      ? (profile.interests as string[]).slice(0, 3)
      : undefined;

    return {
      type: 'CONNECTION_SUGGESTION',
      suggestionId: payload.suggestionId,
      eventId: payload.eventId,
      targetUserId: payload.recipientUserId,
      suggestedUserId: payload.suggestedUserId,
      suggestedUserName,
      suggestedUserAvatar: user?.avatarUrl || undefined,
      suggestedUserTitle: profile?.currentRole || undefined,
      suggestedUserCompany: profile?.company || undefined,
      reason: payload.matchReasons[0] || 'Great networking match',
      matchScore: payload.matchScore,
      sharedInterests,
      conversationStarter: payload.suggestedIceBreaker,
      timestamp: payload.timestamp,
    };
  }

  /**
   * Check if consumer is connected
   */
  isActive(): boolean {
    return this.isConnected;
  }
}
