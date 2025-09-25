import {
  Injectable,
  OnModuleInit,
  OnModuleDestroy,
  Logger,
} from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { Kafka, Consumer, EachMessagePayload } from 'kafkajs';

@Injectable()
export class KafkaConsumerService implements OnModuleInit, OnModuleDestroy {
  private readonly kafka: Kafka;
  private readonly consumer: Consumer;
  private readonly logger = new Logger(KafkaConsumerService.name);

  constructor(
    private readonly configService: ConfigService,
    private readonly eventEmitter: EventEmitter2,
  ) {
    const kafkaBroker = this.configService.getOrThrow<string>(
      'KAFKA_BOOTSTRAP_SERVERS',
    );
    this.kafka = new Kafka({
      brokers: [kafkaBroker],
    });
    this.consumer = this.kafka.consumer({ groupId: 'real-time-service-group' });
  }

  async onModuleInit() {
    this.logger.log('Initializing Kafka consumer...');
    await this.consumer.connect();

    await this.consumer.subscribe({
      topic: 'platform.analytics.check-in.v1',
      fromBeginning: false,
    });

    await this.consumer.run({
      eachMessage: async ({ topic, message }: EachMessagePayload) => {
        if (!message.value) {
          this.logger.warn(
            `Received message with null value on topic '${topic}'`,
          );
          return;
        }

        try {
          // By explicitly typing the payload, we resolve the 'any' warning
          const payload: unknown = JSON.parse(message.value.toString());
          this.logger.log(`Received message from Kafka on topic '${topic}'`);
          this.eventEmitter.emit('analytics-events', payload);
        } catch (error) {
          this.logger.error(
            `Failed to process Kafka message from topic '${topic}'`,
            error,
          );
        }
      },
    });
    this.logger.log('Kafka consumer is running and subscribed to topics.');
  }

  async onModuleDestroy() {
    this.logger.log('Disconnecting Kafka consumer...');
    await this.consumer.disconnect();
  }
}
