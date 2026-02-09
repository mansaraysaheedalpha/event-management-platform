// src/networking/breakout/daily.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';

interface DailyRoom {
  id: string;
  name: string;
  url: string;
  created_at: string;
  config: {
    exp?: number;
    nbf?: number;
    max_participants?: number;
  };
}

interface DailyMeetingToken {
  token: string;
}

@Injectable()
export class DailyService {
  private readonly logger = new Logger(DailyService.name);
  private readonly apiKey: string;
  private readonly baseUrl = 'https://api.daily.co/v1';

  constructor(private configService: ConfigService) {
    this.apiKey = this.configService.get<string>('DAILY_API_KEY') || '';
    if (!this.apiKey) {
      this.logger.warn('DAILY_API_KEY not configured - video rooms will not work');
    }
  }

  /**
   * Creates a new Daily.co room for a breakout session
   */
  async createRoom(options: {
    name: string;
    maxParticipants?: number;
    expiryMinutes?: number;
    enableRecording?: boolean;
  }): Promise<DailyRoom | null> {
    if (!this.apiKey) {
      this.logger.warn('Cannot create room - DAILY_API_KEY not configured');
      return null;
    }

    try {
      // Generate a unique room name (Daily requires alphanumeric + hyphens)
      const roomName = `breakout-${options.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}-${Date.now()}`;

      const expiryTime = options.expiryMinutes
        ? Math.floor(Date.now() / 1000) + (options.expiryMinutes * 60)
        : Math.floor(Date.now() / 1000) + (60 * 60); // Default 1 hour

      const response = await fetch(`${this.baseUrl}/rooms`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify({
          name: roomName,
          privacy: 'private', // Requires token to join
          properties: {
            exp: expiryTime,
            max_participants: options.maxParticipants || 10,
            enable_chat: true,
            enable_screenshare: true,
            ...(options.enableRecording ? { enable_recording: 'cloud' } : {}),
            start_video_off: false,
            start_audio_off: false,
          },
        }),
      });

      if (!response.ok) {
        const error = await response.text();
        this.logger.error(`Failed to create Daily room: ${error}`);
        return null;
      }

      const room: DailyRoom = await response.json();
      this.logger.log(`Created Daily room: ${room.name} (${room.url})`);
      return room;
    } catch (error) {
      this.logger.error('Error creating Daily room:', error);
      return null;
    }
  }

  /**
   * Creates a meeting token for a user to join a room
   */
  async createMeetingToken(options: {
    roomName: string;
    userName: string;
    userId: string;
    isOwner?: boolean;
    expiryMinutes?: number;
    enableScreenShare?: boolean;
    startVideoOff?: boolean;
    startAudioOff?: boolean;
  }): Promise<string | null> {
    if (!this.apiKey) {
      this.logger.warn('Cannot create token - DAILY_API_KEY not configured');
      return null;
    }

    try {
      const expiryTime = options.expiryMinutes
        ? Math.floor(Date.now() / 1000) + (options.expiryMinutes * 60)
        : Math.floor(Date.now() / 1000) + (60 * 60); // Default 1 hour

      const tokenPayload = {
        properties: {
          room_name: options.roomName,
          user_name: options.userName,
          user_id: options.userId,
          is_owner: options.isOwner || false,
          exp: expiryTime,
          enable_screenshare: options.enableScreenShare ?? true,
          start_video_off: options.startVideoOff ?? false,
          start_audio_off: options.startAudioOff ?? false,
        },
      };

      this.logger.log(`Creating Daily.co token with payload: ${JSON.stringify(tokenPayload.properties, null, 2)}`);

      const response = await fetch(`${this.baseUrl}/meeting-tokens`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.apiKey}`,
        },
        body: JSON.stringify(tokenPayload),
      });

      if (!response.ok) {
        const error = await response.text();
        this.logger.error(`Failed to create meeting token: ${error}`);
        return null;
      }

      const data: DailyMeetingToken = await response.json();
      return data.token;
    } catch (error) {
      this.logger.error('Error creating meeting token:', error);
      return null;
    }
  }

  /**
   * Deletes a Daily.co room
   */
  async deleteRoom(roomName: string): Promise<boolean> {
    if (!this.apiKey) {
      return false;
    }

    try {
      const response = await fetch(`${this.baseUrl}/rooms/${roomName}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${this.apiKey}`,
        },
      });

      if (!response.ok && response.status !== 404) {
        const error = await response.text();
        this.logger.error(`Failed to delete Daily room: ${error}`);
        return false;
      }

      this.logger.log(`Deleted Daily room: ${roomName}`);
      return true;
    } catch (error) {
      this.logger.error('Error deleting Daily room:', error);
      return false;
    }
  }

  /**
   * Gets the full URL for joining a room with a token
   */
  getRoomUrl(roomUrl: string, token: string): string {
    return `${roomUrl}?t=${token}`;
  }
}
