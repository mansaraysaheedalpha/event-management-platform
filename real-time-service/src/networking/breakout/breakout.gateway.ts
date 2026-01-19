// src/networking/breakout/breakout.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { BreakoutService } from './breakout.service';
import { CreateRoomDto } from './dto/create-room.dto';
import { JoinRoomDto } from './dto/join-room.dto';
import { LeaveRoomDto } from './dto/leave-room.dto';
import { CloseRoomDto } from './dto/close-room.dto';

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class BreakoutGateway {
  private readonly logger = new Logger(BreakoutGateway.name);
  @WebSocketServer() server: Server;

  // Track active timers for rooms
  private roomTimers: Map<string, NodeJS.Timeout> = new Map();

  // In-memory chat storage (in production, use Redis or database)
  private chatMessages: Map<string, Array<{
    id: string;
    roomId: string;
    userId: string;
    userName: string;
    content: string;
    timestamp: string;
    isSystem?: boolean;
  }>> = new Map();

  constructor(private readonly breakoutService: BreakoutService) {}

  /**
   * Get all breakout rooms for a session.
   */
  @SubscribeMessage('breakout.rooms.list')
  async handleListRooms(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    try {
      const rooms = await this.breakoutService.getRoomsForSession(data.sessionId);
      return { success: true, rooms };
    } catch (error) {
      this.logger.error(`Failed to list breakout rooms: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Create a new breakout room.
   */
  @SubscribeMessage('breakout.room.create')
  async handleCreateRoom(
    @MessageBody() dto: CreateRoomDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    // Check permission
    const hasPermission = user.permissions?.includes('breakout:manage');
    if (!hasPermission) {
      return { success: false, error: 'You do not have permission to create breakout rooms' };
    }

    try {
      const room = await this.breakoutService.createRoom(user.sub, dto);

      // Broadcast to all in the session
      const sessionRoom = `session:${dto.sessionId}`;
      this.server.to(sessionRoom).emit('breakout.room.created', room);

      this.logger.log(`Breakout room ${room.id} created by ${user.sub}`);
      return { success: true, room };
    } catch (error) {
      this.logger.error(`Failed to create breakout room: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Join a breakout room.
   */
  @SubscribeMessage('breakout.room.join')
  async handleJoinRoom(
    @MessageBody() dto: JoinRoomDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const roomData = await this.breakoutService.joinRoom(user.sub, dto.roomId);

      if (!roomData) {
        return { success: false, error: 'Room not found' };
      }

      // Join the socket room for this breakout
      const breakoutRoom = `breakout:${dto.roomId}`;
      await client.join(breakoutRoom);

      // Broadcast participant update to the breakout room
      this.server.to(breakoutRoom).emit('breakout.participants.update', {
        roomId: dto.roomId,
        participants: roomData.participants,
        participantCount: roomData._count.participants,
      });

      // Also broadcast to session room so the room card updates
      this.server.to(`session:${roomData.sessionId}`).emit('breakout.rooms.updated', {
        roomId: dto.roomId,
        participantCount: roomData._count.participants,
      });

      this.logger.log(`User ${user.sub} joined breakout room ${dto.roomId}`);
      return { success: true, room: roomData };
    } catch (error) {
      this.logger.error(`Failed to join breakout room: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get the video room URL for a breakout room.
   * Returns the Daily.co room URL with a user-specific meeting token.
   */
  @SubscribeMessage('breakout.room.getVideoUrl')
  async handleGetVideoUrl(
    @MessageBody() data: { roomId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const userName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Participant';

      const videoRoom = await this.breakoutService.getVideoRoomUrl(
        data.roomId,
        user.sub,
        userName,
        user.permissions || [],
      );

      if (!videoRoom) {
        return {
          success: false,
          error: 'Video room not available. Make sure the room is active and you have joined it.',
        };
      }

      this.logger.log(`Video URL generated for user ${user.sub} in room ${data.roomId}`);
      return {
        success: true,
        videoUrl: videoRoom.url,
        token: videoRoom.token,
        // Full URL with token for convenience
        joinUrl: `${videoRoom.url}?t=${videoRoom.token}`,
      };
    } catch (error) {
      this.logger.error(`Failed to get video URL: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Leave a breakout room.
   */
  @SubscribeMessage('breakout.room.leave')
  async handleLeaveRoom(
    @MessageBody() dto: LeaveRoomDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const roomData = await this.breakoutService.leaveRoom(user.sub, dto.roomId);

      if (!roomData) {
        return { success: false, error: 'Room not found' };
      }

      // Leave the socket room
      const breakoutRoom = `breakout:${dto.roomId}`;
      await client.leave(breakoutRoom);

      // Broadcast participant update
      this.server.to(breakoutRoom).emit('breakout.participants.update', {
        roomId: dto.roomId,
        participants: roomData.participants,
        participantCount: roomData._count.participants,
      });

      // Update session room
      this.server.to(`session:${roomData.sessionId}`).emit('breakout.rooms.updated', {
        roomId: dto.roomId,
        participantCount: roomData._count.participants,
      });

      this.logger.log(`User ${user.sub} left breakout room ${dto.roomId}`);
      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to leave breakout room: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Start the breakout room timer.
   */
  @SubscribeMessage('breakout.room.start')
  async handleStartRoom(
    @MessageBody() data: { roomId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const room = await this.breakoutService.startRoom(
        data.roomId,
        user.sub,
        user.permissions || [],
      );

      const breakoutRoom = `breakout:${data.roomId}`;

      const sessionRoom = `session:${room.sessionId}`;
      const startedPayload = {
        roomId: data.roomId,
        startedAt: room.startedAt,
        durationMinutes: room.durationMinutes,
        videoRoomUrl: room.videoRoomUrl,
        hasVideo: !!room.videoRoomUrl,
      };

      // Broadcast that room has started to both breakout room and session room
      this.server.to(breakoutRoom).emit('breakout.room.started', startedPayload);
      this.server.to(sessionRoom).emit('breakout.room.started', startedPayload);

      // Also emit the rooms.updated event for legacy compatibility
      this.server.to(sessionRoom).emit('breakout.rooms.updated', {
        roomId: data.roomId,
        status: 'ACTIVE',
        startedAt: room.startedAt,
        videoRoomUrl: room.videoRoomUrl,
        hasVideo: !!room.videoRoomUrl,
      });

      // Start the timer
      this.startRoomTimer(data.roomId, room.sessionId, room.durationMinutes);

      this.logger.log(`Breakout room ${data.roomId} started by ${user.sub}`);
      return { success: true, room };
    } catch (error) {
      this.logger.error(`Failed to start breakout room: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Close a breakout room.
   */
  @SubscribeMessage('breakout.room.close')
  async handleCloseRoom(
    @MessageBody() dto: CloseRoomDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const room = await this.breakoutService.closeRoom(
        dto.roomId,
        user.sub,
        user.permissions || [],
      );

      // Cancel any active timer
      this.cancelRoomTimer(dto.roomId);

      // Broadcast room closure to participants
      const breakoutRoom = `breakout:${dto.roomId}`;
      this.server.to(breakoutRoom).emit('breakout.room.closed', {
        roomId: dto.roomId,
      });

      // Update session room
      this.server.to(`session:${room.sessionId}`).emit('breakout.room.closed', {
        roomId: dto.roomId,
      });

      this.logger.log(`Breakout room ${dto.roomId} closed by ${user.sub}`);
      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to close breakout room: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Recall all participants from all breakout rooms back to main session.
   */
  @SubscribeMessage('breakout.all.recall')
  async handleRecallAll(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const closedRoomIds = await this.breakoutService.closeAllRooms(
        data.sessionId,
        user.sub,
        user.permissions || [],
      );

      // Cancel all timers and notify all rooms
      for (const roomId of closedRoomIds) {
        this.cancelRoomTimer(roomId);
        this.server.to(`breakout:${roomId}`).emit('breakout.recalled', {
          message: 'All breakout rooms have been closed. Please return to the main session.',
        });
      }

      // Broadcast to session
      this.server.to(`session:${data.sessionId}`).emit('breakout.all.recalled', {
        closedRoomIds,
      });

      this.logger.log(`All breakout rooms recalled for session ${data.sessionId} by ${user.sub}`);
      return { success: true, closedRoomIds };
    } catch (error) {
      this.logger.error(`Failed to recall all breakout rooms: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Send a chat message in a breakout room.
   */
  @SubscribeMessage('breakout.chat.send')
  async handleChatSend(
    @MessageBody() data: { roomId: string; content: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!data.content?.trim()) {
      return { success: false, error: 'Message cannot be empty' };
    }

    try {
      const userName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Participant';

      const message = {
        id: `msg-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        roomId: data.roomId,
        userId: user.sub,
        userName,
        content: data.content.trim(),
        timestamp: new Date().toISOString(),
      };

      // Store message
      if (!this.chatMessages.has(data.roomId)) {
        this.chatMessages.set(data.roomId, []);
      }
      const messages = this.chatMessages.get(data.roomId)!;
      messages.push(message);

      // Keep only last 100 messages per room
      if (messages.length > 100) {
        messages.shift();
      }

      // Broadcast to room
      this.server.to(`breakout:${data.roomId}`).emit('breakout.chat.message', message);

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to send chat message: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get chat history for a breakout room.
   */
  @SubscribeMessage('breakout.chat.getHistory')
  async handleChatHistory(
    @MessageBody() data: { roomId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    try {
      const messages = this.chatMessages.get(data.roomId) || [];
      return { success: true, roomId: data.roomId, messages };
    } catch (error) {
      this.logger.error(`Failed to get chat history: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Start the countdown timer for a room.
   */
  private startRoomTimer(roomId: string, sessionId: string, durationMinutes: number) {
    // Clear any existing timer
    this.cancelRoomTimer(roomId);

    const durationMs = durationMinutes * 60 * 1000;
    const warningTimes = [5 * 60 * 1000, 1 * 60 * 1000]; // 5 min and 1 min warnings
    const breakoutRoom = `breakout:${roomId}`;

    // Set up warning timers
    warningTimes.forEach((warningMs) => {
      if (durationMs > warningMs) {
        const warningTimeout = setTimeout(() => {
          const minutesRemaining = Math.round(warningMs / 60000);
          this.server.to(breakoutRoom).emit('breakout.timer.warning', {
            roomId,
            minutesRemaining,
            message: `${minutesRemaining} minute${minutesRemaining > 1 ? 's' : ''} remaining`,
          });

          // Set CLOSING status at 1 minute warning
          if (minutesRemaining === 1) {
            this.breakoutService.setRoomClosing(roomId).catch((err) => {
              this.logger.error(`Failed to set room closing: ${err.message}`);
            });
          }
        }, durationMs - warningMs);

        // We don't track warning timeouts separately, they'll be cancelled with the main timer
      }
    });

    // Set up end timer
    const endTimeout = setTimeout(async () => {
      try {
        // Auto-close the room
        await this.breakoutService.closeRoom(roomId, 'system', ['breakout:manage']);

        this.server.to(breakoutRoom).emit('breakout.room.closed', {
          roomId,
          reason: 'timer',
        });

        this.server.to(`session:${sessionId}`).emit('breakout.room.closed', {
          roomId,
          reason: 'timer',
        });

        this.logger.log(`Breakout room ${roomId} auto-closed due to timer`);
      } catch (error) {
        this.logger.error(`Failed to auto-close room ${roomId}: ${getErrorMessage(error)}`);
      }
    }, durationMs);

    this.roomTimers.set(roomId, endTimeout);
  }

  /**
   * Cancel the timer for a room.
   */
  private cancelRoomTimer(roomId: string) {
    const timer = this.roomTimers.get(roomId);
    if (timer) {
      clearTimeout(timer);
      this.roomTimers.delete(roomId);
    }
  }
}
