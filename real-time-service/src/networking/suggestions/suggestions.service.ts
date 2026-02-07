//src/networking/suggestions/suggestions.service.ts
import { Inject, Injectable, Logger, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { AiSuggestionPayload, SuggestionsGateway } from './suggestions.gateway';
import { KafkaSuggestionConsumerService } from 'src/shared/kafka/kafka-suggestion-consumer.service';

@Injectable()
export class SuggestionsService {
  private readonly logger = new Logger(SuggestionsService.name);

  constructor(
    @Inject(forwardRef(() => SuggestionsGateway))
    private readonly suggestionsGateway: SuggestionsGateway,
    // Inject Kafka consumer to ensure it gets instantiated
    private readonly kafkaConsumer: KafkaSuggestionConsumerService,
  ) {
    this.logger.log(
      `Kafka consumer active: ${this.kafkaConsumer.isActive()}`,
    );
  }

  @OnEvent('ai-suggestions')
  handleAiSuggestion(payload: AiSuggestionPayload) {
    this.logger.log(`Processing AI suggestion: ${payload.type}`);

    // The service's job is to route the event to the gateway
    this.suggestionsGateway.sendSuggestion(payload);
  }
}
