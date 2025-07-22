import { HttpService } from '@nestjs/axios';
import { Inject, Injectable, Logger, NotFoundException } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Redis } from 'ioredis';
import { PrismaService } from 'src/prisma.service';
import { REDIS_CLIENT } from 'src/shared/shared.module';
import { firstValueFrom } from 'rxjs';

// NEW: Define the shape of the expected API response
interface GoogleTranslateResponse {
  data: {
    translations: {
      translatedText: string;
    }[];
  };
}

@Injectable()
export class TranslationService {
  private readonly logger = new Logger(TranslationService.name);
  private readonly CACHE_TTL = 3600; // Cache translations for 1 hour

  constructor(
    private readonly prisma: PrismaService,
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
    @Inject(REDIS_CLIENT) private readonly redis: Redis,
  ) {}

  async getTranslation(
    messageId: string,
    targetLanguage: string,
  ): Promise<string> {
    const cacheKey = `translation:${messageId}:${targetLanguage}`;

    // 1. Check cache first
    const cachedTranslation = await this.redis.get(cacheKey);
    if (cachedTranslation) {
      this.logger.log(
        `Cache hit for translation of message ${messageId} to ${targetLanguage}`,
      );
      return cachedTranslation;
    }

    this.logger.log(
      `Cache miss for translation of message ${messageId}. Fetching from DB and API.`,
    );

    // 2. On cache miss, get the original message from our database
    const message = await this.prisma.message.findUnique({
      where: { id: messageId },
      select: { text: true },
    });

    if (!message) {
      throw new NotFoundException('Original message not found.');
    }

    // 3. Call the external translation API
    const translatedText = await this._fetchFromExternalApi(
      message.text,
      targetLanguage,
    );

    // 4. Store the new translation in the cache for next time
    await this.redis.set(cacheKey, translatedText, 'EX', this.CACHE_TTL);

    return translatedText;
  }

  private async _fetchFromExternalApi(
    text: string,
    target: string,
  ): Promise<string> {
    // This is a mock implementation. You would replace this with the actual
    // SDK or API call for your chosen translation service (e.g., Google Translate).
    const apiKey = this.configService.get<string>('TRANSLATION_API_KEY');
    const apiUrl = `https://translation.googleapis.com/language/translate/v2`;

    try {
      const response = await firstValueFrom(
        this.httpService.post<GoogleTranslateResponse>(
          apiUrl,
          {
            q: text,
            target: target,
          },
          { params: { key: apiKey } },
        ),
      );
      return response.data.data.translations[0].translatedText;
    } catch (error) {
      this.logger.error('Failed to fetch from Translation API', error);
      // Fallback to original text if translation fails
      return text;
    }
  }
}
