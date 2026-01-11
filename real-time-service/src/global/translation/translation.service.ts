//src/global/translation/translation.service.ts
import { HttpService } from '@nestjs/axios';
import { Inject, Injectable, Logger, NotFoundException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Redis } from 'ioredis';
import { PrismaService } from 'src/prisma.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { firstValueFrom } from 'rxjs';
import { AxiosError } from 'axios';

interface GoogleTranslateResponse {
  data: {
    translations: {
      translatedText: string;
    }[];
  };
}

// Type to indicate if the API call succeeded
type TranslationResult = {
  text: string;
  isSuccess: boolean;
};

// Metrics keys for monitoring
const METRICS_PREFIX = 'metrics:translation';

/**
 * Service for handling message translation using Google Translate API
 * and caching results with Redis.
 *
 * Monitoring: Track these Redis keys for alerting:
 * - metrics:translation:success - Total successful translations
 * - metrics:translation:failure - Total failed translations
 * - metrics:translation:cache_hit - Cache hits
 * - metrics:translation:cache_miss - Cache misses
 */

@Injectable()
export class TranslationService {
  private readonly logger = new Logger(TranslationService.name);
  private readonly CACHE_TTL = 3600;

  constructor(
    private readonly prisma: PrismaService,
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  /**
   * Get a translated message from cache or API.
   * @param messageId - ID of the message to translate
   * @param targetLanguage - Language to translate the message into
   * @returns The translated message text
   */

  async getTranslation(
    messageId: string,
    targetLanguage: string,
  ): Promise<string> {
    const cacheKey = `translation:${messageId}:${targetLanguage}`;
    const cachedTranslation = await this.redis.get(cacheKey);
    if (cachedTranslation) {
      this.logger.log(`Cache hit for message ${messageId}`);
      await this.incrementMetric('cache_hit');
      return cachedTranslation;
    }

    this.logger.log(`Cache miss for message ${messageId}. Fetching...`);
    await this.incrementMetric('cache_miss');

    const message = await this.prisma.message.findUnique({
      where: { id: messageId },
      select: { text: true },
    });
    if (!message) {
      throw new NotFoundException('Original message not found.');
    }

    const translationResult = await this._fetchFromExternalApi(
      message.text,
      targetLanguage,
    );

    // Only store the translation in the cache if the API call was successful.
    if (translationResult.isSuccess) {
      await this.redis.set(
        cacheKey,
        translationResult.text,
        'EX',
        this.CACHE_TTL,
      );
    }

    return translationResult.text;
  }

  /**
   * Increment a metric counter in Redis for monitoring.
   */
  private async incrementMetric(metric: string): Promise<void> {
    try {
      await this.redis.incr(`${METRICS_PREFIX}:${metric}`);
    } catch (error) {
      // Don't fail the main operation if metrics fail
      this.logger.warn(`Failed to increment metric ${metric}`);
    }
  }

  /**
   * Fetch translation from external Google Translate API.
   * @param text - Original message text
   * @param target - Target language code
   * @returns Translated message text
   */
  private async _fetchFromExternalApi(
    text: string,
    target: string,
  ): Promise<TranslationResult> {
    const apiKey = this.configService.get<string>('TRANSLATION_API_KEY');
    const apiUrl = `https://translation.googleapis.com/language/translate/v2`;

    try {
      const response = await firstValueFrom(
        this.httpService.post<GoogleTranslateResponse>(
          apiUrl,
          { q: text, target: target },
          { params: { key: apiKey } },
        ),
      );
      const translatedText = response.data.data.translations[0].translatedText;
      return { text: translatedText, isSuccess: true }; // Return success object
    } catch (error) {
      this.logger.error('Failed to fetch from Translation API', error);
      // **FIX**: Return failure object with original text
      return { text: text, isSuccess: false };
    }
  }
}
