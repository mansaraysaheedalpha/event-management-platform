// src/virtual-stage/virtual-stage.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { DailyService } from '../networking/breakout/daily.service';
import { CreateStageRoomDto } from './dto/create-stage-room.dto';

@Injectable()
export class VirtualStageService {
  private readonly logger = new Logger(VirtualStageService.name);

  constructor(private readonly dailyService: DailyService) {}

  /**
   * Create a Daily room for a virtual session.
   * Returns the room name and URL to store on the session record.
   */
  async createSessionRoom(
    dto: CreateStageRoomDto,
  ): Promise<{ roomName: string; roomUrl: string } | null> {
    this.logger.log(
      `Creating Daily room for session ${dto.sessionId} ("${dto.sessionTitle}")`,
    );

    const room = await this.dailyService.createRoom({
      name: `stage-${dto.sessionId}`,
      maxParticipants: dto.maxParticipants || 200,
      expiryMinutes: dto.expiryMinutes || 480, // 8 hours default
      enableRecording: dto.enableRecording ?? false,
    });

    if (!room) {
      this.logger.error(`Failed to create Daily room for session ${dto.sessionId}`);
      return null;
    }

    this.logger.log(`Created Daily room ${room.name} for session ${dto.sessionId}`);
    return { roomName: room.name, roomUrl: room.url };
  }

  /**
   * Generate a meeting token for a user to join the session.
   * Speakers get isOwner=true (can screenshare, mute others, etc.)
   * Attendees get isOwner=false. For broadcast-only sessions, attendees
   * join with video/audio off and no screenshare.
   */
  async generateToken(options: {
    roomName: string;
    userId: string;
    userName: string;
    isSpeaker: boolean;
    broadcastOnly?: boolean;
    sessionDurationMinutes?: number;
  }): Promise<string | null> {
    const isAttendeeInBroadcast = !options.isSpeaker && options.broadcastOnly;

    return this.dailyService.createMeetingToken({
      roomName: options.roomName,
      userName: options.userName,
      userId: options.userId,
      isOwner: options.isSpeaker,
      expiryMinutes: options.sessionDurationMinutes || 480,
      enableScreenShare: options.isSpeaker, // Only speakers can screenshare
      startVideoOff: isAttendeeInBroadcast,
      startAudioOff: isAttendeeInBroadcast,
    });
  }

  /**
   * Delete the Daily room (cleanup when session ends).
   */
  async deleteSessionRoom(roomName: string): Promise<boolean> {
    this.logger.log(`Deleting Daily room: ${roomName}`);
    return this.dailyService.deleteRoom(roomName);
  }
}
