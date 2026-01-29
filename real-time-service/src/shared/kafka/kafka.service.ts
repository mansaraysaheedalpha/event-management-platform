import { Injectable, OnModuleInit, OnModuleDestroy, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Kafka, Producer, logLevel, SASLOptions } from 'kafkajs';

// Kafka Topics
export const KAFKA_TOPICS = {
  GIVEAWAY_EVENTS: 'giveaway.events.v1',
  LEAD_CAPTURE_EVENTS: 'lead.capture.events.v1',
  LEAD_INTENT_EVENTS: 'lead.intent.events.v1',
} as const;

// Lead capture event types
export interface LeadCaptureEvent {
  type: 'LEAD_CAPTURED';
  sponsorId: string;
  eventId: string;
  userId: string;
  boothId: string;
  formData: {
    name?: string;
    email?: string;
    company?: string;
    jobTitle?: string;
    phone?: string;
    interests?: string;
    message?: string;
    marketingConsent?: boolean;
  };
  timestamp: string;
}

// Lead interaction event for ongoing engagement (updates intent score for existing leads)
export interface LeadInteractionEvent {
  type: 'LEAD_INTERACTION';
  sponsorId: string;
  eventId: string;
  userId: string;
  boothId: string;
  interactionType: 'content_download' | 'content_view' | 'cta_click' | 'demo_watched' | 'video_session' | 'chat_message' | 'booth_visit';
  interactionMetadata: {
    resourceId?: string;
    resourceName?: string;
    ctaId?: string;
    ctaLabel?: string;
    videoDurationSeconds?: number;
    videoCompleted?: boolean;
    visitDurationSeconds?: number;
  };
  timestamp: string;
}

// Giveaway event types
export interface GiveawayWinnerEmailEvent {
  type: 'GIVEAWAY_WINNER_SINGLE_POLL' | 'GIVEAWAY_WINNER_QUIZ';
  giveawayWinnerId: string;
  winnerEmail: string;
  winnerName: string;
  eventId: string;
  eventName: string;
  sessionId: string;
  sessionName?: string;
  // Prize details
  prizeTitle?: string;
  prizeDescription?: string;
  claimInstructions?: string;
  claimLocation?: string;
  claimDeadline?: string;
  // Quiz-specific
  quizScore?: number;
  quizTotal?: number;
  // Poll-specific
  winningOptionText?: string;
}

@Injectable()
export class KafkaService implements OnModuleInit, OnModuleDestroy {
  private readonly logger = new Logger(KafkaService.name);
  private kafka: Kafka;
  private producer: Producer;
  private isConnected = false;

  constructor(private readonly configService: ConfigService) {
    const brokers = this.configService.get<string>('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092').split(',');
    const kafkaApiKey = this.configService.get<string>('KAFKA_API_KEY');
    const kafkaApiSecret = this.configService.get<string>('KAFKA_API_SECRET');

    // Build Kafka configuration with optional SASL authentication (for Confluent Cloud)
    const kafkaConfig: ConstructorParameters<typeof Kafka>[0] = {
      clientId: 'real-time-service',
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
      this.logger.log('Kafka configured with SASL_SSL authentication');
    }

    this.kafka = new Kafka(kafkaConfig);

    this.producer = this.kafka.producer({
      allowAutoTopicCreation: true,
    });
  }

  async onModuleInit() {
    try {
      await this.producer.connect();
      this.isConnected = true;
      this.logger.log('Kafka producer connected successfully');
    } catch (error) {
      this.logger.error('Failed to connect Kafka producer:', error);
      // Don't throw - allow service to start even if Kafka is unavailable
    }
  }

  async onModuleDestroy() {
    try {
      await this.producer.disconnect();
      this.logger.log('Kafka producer disconnected');
    } catch (error) {
      this.logger.error('Error disconnecting Kafka producer:', error);
    }
  }

  /**
   * Send a giveaway winner email event to Kafka
   */
  async sendGiveawayWinnerEmail(event: GiveawayWinnerEmailEvent): Promise<boolean> {
    if (!this.isConnected) {
      this.logger.warn('Kafka not connected, skipping email event');
      return false;
    }

    try {
      await this.producer.send({
        topic: KAFKA_TOPICS.GIVEAWAY_EVENTS,
        messages: [
          {
            key: event.giveawayWinnerId,
            value: JSON.stringify(event),
          },
        ],
      });

      this.logger.log(`Giveaway winner email event sent for winner: ${event.winnerName} (${event.winnerEmail})`);
      return true;
    } catch (error) {
      this.logger.error('Failed to send giveaway winner email event:', error);
      return false;
    }
  }

  /**
   * Send a lead capture event to Kafka
   * This replaces the synchronous HTTP call to event-lifecycle-service
   */
  async sendLeadCaptureEvent(event: LeadCaptureEvent): Promise<boolean> {
    if (!this.isConnected) {
      this.logger.warn('Kafka not connected, skipping lead capture event');
      return false;
    }

    try {
      await this.producer.send({
        topic: KAFKA_TOPICS.LEAD_CAPTURE_EVENTS,
        messages: [
          {
            key: event.sponsorId,
            value: JSON.stringify(event),
          },
        ],
      });

      this.logger.log(
        `Lead capture event sent for sponsor ${event.sponsorId}, booth ${event.boothId}`,
      );
      return true;
    } catch (error) {
      this.logger.error('Failed to send lead capture event:', error);
      return false;
    }
  }

  /**
   * Send a lead interaction event to Kafka
   * This updates intent scores for existing leads based on engagement
   */
  async sendLeadInteractionEvent(event: LeadInteractionEvent): Promise<boolean> {
    if (!this.isConnected) {
      this.logger.warn('Kafka not connected, skipping lead interaction event');
      return false;
    }

    try {
      await this.producer.send({
        topic: KAFKA_TOPICS.LEAD_CAPTURE_EVENTS, // Same topic, different event type
        messages: [
          {
            key: event.sponsorId,
            value: JSON.stringify(event),
          },
        ],
      });

      this.logger.log(
        `Lead interaction event sent: ${event.interactionType} for sponsor ${event.sponsorId}, user ${event.userId}`,
      );
      return true;
    } catch (error) {
      this.logger.error('Failed to send lead interaction event:', error);
      return false;
    }
  }

  /**
   * Generic method to send any event to a topic
   */
  async sendEvent(topic: string, key: string, event: Record<string, unknown>): Promise<boolean> {
    if (!this.isConnected) {
      this.logger.warn(`Kafka not connected, skipping event to topic: ${topic}`);
      return false;
    }

    try {
      await this.producer.send({
        topic,
        messages: [
          {
            key,
            value: JSON.stringify(event),
          },
        ],
      });

      this.logger.log(`Event sent to topic ${topic} with key: ${key}`);
      return true;
    } catch (error) {
      this.logger.error(`Failed to send event to topic ${topic}:`, error);
      return false;
    }
  }
}
