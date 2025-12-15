//src/shared/services/session-settings.service.ts
import { Injectable, Logger, OnModuleInit } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { firstValueFrom } from 'rxjs';

export interface SessionSettings {
  id: string;
  event_id: string;
  title: string;
  chat_enabled: boolean;
  qa_enabled: boolean;
  polls_enabled: boolean;
  chat_open: boolean;
  qa_open: boolean;
  polls_open: boolean;
}

/**
 * SessionSettingsService fetches session configuration from the event-lifecycle-service.
 * Used to check if Chat/Q&A is enabled for a specific session before allowing actions.
 */
@Injectable()
export class SessionSettingsService implements OnModuleInit {
  private readonly logger = new Logger(SessionSettingsService.name);
  private readonly eventServiceUrl: string;
  private readonly internalApiKey: string;

  // Simple in-memory cache to avoid repeated API calls (TTL: 30 seconds)
  private cache: Map<string, { data: SessionSettings; expiry: number }> =
    new Map();
  private readonly cacheTtlMs = 30000; // 30 seconds

  constructor(
    private readonly httpService: HttpService,
    private readonly configService: ConfigService,
  ) {
    this.eventServiceUrl = this.configService.get<string>(
      'EVENT_LIFECYCLE_SERVICE_URL',
      'http://localhost:8000',
    );
    this.internalApiKey =
      this.configService.getOrThrow<string>('INTERNAL_API_KEY');
  }

  onModuleInit() {
    this.logger.log(
      'SessionSettingsService initialized with INTERNAL_API_KEY configured',
    );
  }

  /**
   * Fetches session settings from the event-lifecycle-service.
   * Results are cached for 30 seconds to reduce API calls.
   * @param sessionId - The ID of the session to fetch settings for.
   * @returns Session settings including chat_enabled and qa_enabled.
   */
  async getSessionSettings(sessionId: string): Promise<SessionSettings | null> {
    // Check cache first
    const cached = this.cache.get(sessionId);
    if (cached && cached.expiry > Date.now()) {
      this.logger.debug(`Cache hit for session ${sessionId}`);
      return cached.data;
    }

    // Remove /graphql suffix if present
    const baseUrl = this.eventServiceUrl.replace('/graphql', '');

    try {
      const response = await firstValueFrom(
        this.httpService.get<SessionSettings>(
          `${baseUrl}/api/v1/internal/sessions/${sessionId}/details`,
          {
            headers: {
              'X-Internal-Api-Key': this.internalApiKey,
            },
            timeout: 3000,
          },
        ),
      );

      const settings = response.data;
      this.logger.debug(
        `Fetched settings for session ${sessionId}: chat_enabled=${settings.chat_enabled}, chat_open=${settings.chat_open}, qa_enabled=${settings.qa_enabled}, qa_open=${settings.qa_open}, polls_enabled=${settings.polls_enabled}, polls_open=${settings.polls_open}`,
      );

      // Cache the result
      this.cache.set(sessionId, {
        data: settings,
        expiry: Date.now() + this.cacheTtlMs,
      });

      return settings;
    } catch (error: any) {
      if (error.response?.status === 404) {
        this.logger.warn(`Session ${sessionId} not found`);
        return null;
      }

      // For network errors, log and return null (allow degraded mode)
      this.logger.error(
        `Failed to fetch session settings for ${sessionId}: ${error.message}. Allowing with degraded validation.`,
      );

      // Return default settings (enabled but closed) on network errors
      return {
        id: sessionId,
        event_id: '',
        title: '',
        chat_enabled: true,
        qa_enabled: true,
        polls_enabled: true,
        chat_open: false,
        qa_open: false,
        polls_open: false,
      };
    }
  }

  /**
   * Checks if chat is enabled for a session.
   * @param sessionId - The ID of the session to check.
   * @returns True if chat is enabled, false otherwise.
   */
  async isChatEnabled(sessionId: string): Promise<boolean> {
    const settings = await this.getSessionSettings(sessionId);
    return settings?.chat_enabled ?? true; // Default to true if unknown
  }

  /**
   * Checks if Q&A is enabled for a session.
   * @param sessionId - The ID of the session to check.
   * @returns True if Q&A is enabled, false otherwise.
   */
  async isQaEnabled(sessionId: string): Promise<boolean> {
    const settings = await this.getSessionSettings(sessionId);
    return settings?.qa_enabled ?? true; // Default to true if unknown
  }

  /**
   * Checks if chat is currently active (both enabled AND open).
   * @param sessionId - The ID of the session to check.
   * @returns True if chat is enabled and open, false otherwise.
   */
  async isChatActive(sessionId: string): Promise<boolean> {
    const settings = await this.getSessionSettings(sessionId);
    if (!settings) return false;
    return settings.chat_enabled && settings.chat_open;
  }

  /**
   * Checks if Q&A is currently active (both enabled AND open).
   * @param sessionId - The ID of the session to check.
   * @returns True if Q&A is enabled and open, false otherwise.
   */
  async isQaActive(sessionId: string): Promise<boolean> {
    const settings = await this.getSessionSettings(sessionId);
    if (!settings) return false;
    return settings.qa_enabled && settings.qa_open;
  }

  /**
   * Checks if polls are enabled for a session.
   * @param sessionId - The ID of the session to check.
   * @returns True if polls are enabled, false otherwise.
   */
  async isPollsEnabled(sessionId: string): Promise<boolean> {
    const settings = await this.getSessionSettings(sessionId);
    return settings?.polls_enabled ?? true; // Default to true if unknown
  }

  /**
   * Checks if polls are currently active (both enabled AND open).
   * @param sessionId - The ID of the session to check.
   * @returns True if polls are enabled and open, false otherwise.
   */
  async isPollsActive(sessionId: string): Promise<boolean> {
    const settings = await this.getSessionSettings(sessionId);
    if (!settings) return false;
    return settings.polls_enabled && settings.polls_open;
  }

  /**
   * Clears the cache for a specific session (useful when settings are updated).
   * @param sessionId - The ID of the session to clear from cache.
   */
  clearCache(sessionId: string): void {
    this.cache.delete(sessionId);
    this.logger.debug(`Cache cleared for session ${sessionId}`);
  }
}
