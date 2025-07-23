import {
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
} from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { TranslationService } from './translation.service';
import { RequestTranslationDto } from '../dto/request-translation.dto';

/**
 * WebSocket Gateway for translation requests via '/events' namespace.
 */
@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class TranslationGateway {
  private readonly logger = new Logger(TranslationGateway.name);

  constructor(private readonly translationService: TranslationService) {}

  /**
   * Handle incoming translation requests via WebSocket.
   * @param dto - Request payload containing message ID and target language
   * @returns Translated message data or error response
   */
  @SubscribeMessage('translation.request')
  async handleTranslationRequest(@MessageBody() dto: RequestTranslationDto) {
    try {
      const translatedText = await this.translationService.getTranslation(
        dto.messageId,
        dto.targetLanguage,
      );

      // Respond directly and only to the client that made the request.
      return {
        success: true,
        event: 'translation.response',
        data: {
          messageId: dto.messageId,
          targetLanguage: dto.targetLanguage,
          translatedText: translatedText,
        },
      };
    } catch (error) {
      this.logger.error(
        `Failed to translate message ${dto.messageId} to ${dto.targetLanguage}`,
        getErrorMessage(error),
      );
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
