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
import { SegmentService } from './segment.service';
import { CreateRoomDto } from './dto/create-room.dto';
import { JoinRoomDto } from './dto/join-room.dto';
import { LeaveRoomDto } from './dto/leave-room.dto';
import { CloseRoomDto } from './dto/close-room.dto';
import { AssignmentStatus } from '@prisma/client';

// Rate limiting configuration
interface RateLimitConfig {
  windowMs: number;
  maxRequests: number;
}

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

@WebSocketGateway({
  cors: { origin: true, credentials: true },
  namespace: '/events',
})
export class BreakoutGateway {
  private readonly logger = new Logger(BreakoutGateway.name);
  @WebSocketServer() server: Server;

  // Track active timers for rooms (main timer + warning timers)
  private roomTimers: Map<string, { main: NodeJS.Timeout; warnings: NodeJS.Timeout[] }> = new Map();

  // Mutex for timer operations to prevent race conditions
  private timerLocks: Set<string> = new Set();

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

  // Rate limiting maps per operation type
  private rateLimits: Map<string, RateLimitEntry> = new Map();
  private readonly RATE_LIMIT_CONFIGS: Record<string, RateLimitConfig> = {
    'room.create': { windowMs: 60000, maxRequests: 10 },      // 10 rooms/min
    'room.start': { windowMs: 60000, maxRequests: 20 },       // 20 starts/min
    'room.close': { windowMs: 60000, maxRequests: 20 },       // 20 closes/min
    'all.recall': { windowMs: 60000, maxRequests: 5 },        // 5 recalls/min
    'segment.create': { windowMs: 60000, maxRequests: 20 },   // 20 segments/min
    'assignment.compute': { windowMs: 60000, maxRequests: 5 }, // 5 computes/min
    'assignment.notify': { windowMs: 60000, maxRequests: 10 }, // 10 notifies/min
  };

  /**
   * Check rate limit for a user and operation
   * Returns true if allowed, false if rate limited
   */
  private checkRateLimit(userId: string, operation: string): boolean {
    const config = this.RATE_LIMIT_CONFIGS[operation];
    if (!config) return true; // No limit configured

    const key = `${userId}:${operation}`;
    const now = Date.now();
    const entry = this.rateLimits.get(key);

    if (!entry || now >= entry.resetAt) {
      // New window
      this.rateLimits.set(key, { count: 1, resetAt: now + config.windowMs });
      return true;
    }

    if (entry.count >= config.maxRequests) {
      return false; // Rate limited
    }

    entry.count++;
    return true;
  }

  /**
   * Validate ID format (CUID or UUID).
   * CUID: starts with 'c', 25+ lowercase alphanumeric chars
   * UUID: 36 chars with dashes in specific positions
   */
  private isValidId(id: string): boolean {
    if (!id || typeof id !== 'string') return false;

    // CUID format: starts with 'c', 25+ lowercase alphanumeric
    const cuidRegex = /^c[a-z0-9]{24,}$/;
    if (cuidRegex.test(id)) return true;

    // UUID format: 8-4-4-4-12 with hex chars
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (uuidRegex.test(id)) return true;

    return false;
  }

  constructor(
    private readonly breakoutService: BreakoutService,
    private readonly segmentService: SegmentService,
  ) {}

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

    // Rate limit check
    if (!this.checkRateLimit(user.sub, 'room.create')) {
      this.logger.warn(`Rate limit exceeded for user ${user.sub} on room.create`);
      return { success: false, error: 'Too many requests. Please try again later.' };
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

    // Rate limit check
    if (!this.checkRateLimit(user.sub, 'room.start')) {
      this.logger.warn(`Rate limit exceeded for user ${user.sub} on room.start`);
      return { success: false, error: 'Too many requests. Please try again later.' };
    }

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

    // Rate limit check
    if (!this.checkRateLimit(user.sub, 'room.close')) {
      this.logger.warn(`Rate limit exceeded for user ${user.sub} on room.close`);
      return { success: false, error: 'Too many requests. Please try again later.' };
    }

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

    // Rate limit check - this is an expensive operation
    if (!this.checkRateLimit(user.sub, 'all.recall')) {
      this.logger.warn(`Rate limit exceeded for user ${user.sub} on all.recall`);
      return { success: false, error: 'Too many requests. Please try again later.' };
    }

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

  // Rate limiting: track last message time per user per room
  private chatRateLimits: Map<string, number> = new Map();
  private readonly CHAT_RATE_LIMIT_MS = 500; // Min 500ms between messages
  private readonly MAX_MESSAGE_LENGTH = 1000; // Max 1000 characters per message

  /**
   * Send a chat message in a breakout room.
   */
  @SubscribeMessage('breakout.chat.send')
  async handleChatSend(
    @MessageBody() data: { roomId: string; content: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    // Validate roomId format (CUID or UUID)
    if (!this.isValidId(data.roomId)) {
      return { success: false, error: 'Invalid room ID format' };
    }

    if (!data.content?.trim()) {
      return { success: false, error: 'Message cannot be empty' };
    }

    // Check message length
    const trimmedContent = data.content.trim();
    if (trimmedContent.length > this.MAX_MESSAGE_LENGTH) {
      return { success: false, error: `Message too long (max ${this.MAX_MESSAGE_LENGTH} characters)` };
    }

    // Rate limiting check
    const rateLimitKey = `${user.sub}:${data.roomId}`;
    const lastMessageTime = this.chatRateLimits.get(rateLimitKey) || 0;
    const now = Date.now();
    if (now - lastMessageTime < this.CHAT_RATE_LIMIT_MS) {
      return { success: false, error: 'Please wait before sending another message' };
    }

    try {
      // Verify user is a participant in this room or has manage permission
      const isParticipant = await this.breakoutService.isUserInRoom(data.roomId, user.sub);
      const hasPermission = user.permissions?.includes('breakout:manage');

      if (!isParticipant && !hasPermission) {
        return { success: false, error: 'You must be a participant in this room to send messages' };
      }

      const userName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Participant';

      const message = {
        id: `msg-${Date.now()}-${Math.random().toString(36).substring(2, 11)}`,
        roomId: data.roomId,
        userId: user.sub,
        userName,
        content: trimmedContent,
        timestamp: new Date().toISOString(),
      };

      // Update rate limit
      this.chatRateLimits.set(rateLimitKey, now);

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
    const user = getAuthenticatedUser(client);

    // Validate roomId format (CUID or UUID)
    if (!this.isValidId(data.roomId)) {
      return { success: false, error: 'Invalid room ID format' };
    }

    try {
      // Verify user has access to this room
      const isParticipant = await this.breakoutService.isUserInRoom(data.roomId, user.sub);
      const hasPermission = user.permissions?.includes('breakout:manage');

      if (!isParticipant && !hasPermission) {
        return { success: false, error: 'You do not have access to this room' };
      }

      const messages = this.chatMessages.get(data.roomId) || [];

      // Also emit as event for consistency with message handler
      client.emit('breakout.chat.history', { roomId: data.roomId, messages });

      return { success: true, roomId: data.roomId, messages };
    } catch (error) {
      this.logger.error(`Failed to get chat history: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // Segment Management Handlers
  // ==========================================

  /**
   * Create a new segment for a session.
   */
  @SubscribeMessage('segment.create')
  async handleCreateSegment(
    @MessageBody() data: {
      sessionId: string;
      eventId: string;
      name: string;
      description?: string;
      color?: string;
      matchCriteria?: {
        field: string;
        operator: 'equals' | 'contains' | 'startsWith' | 'in' | 'notEquals';
        value: string | string[];
      };
      priority?: number;
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    // Rate limit check
    if (!this.checkRateLimit(user.sub, 'segment.create')) {
      this.logger.warn(`Rate limit exceeded for user ${user.sub} on segment.create`);
      return { success: false, error: 'Too many requests. Please try again later.' };
    }

    try {
      const segment = await this.segmentService.createSegment(user.sub, data);

      // Broadcast to session
      this.server.to(`session:${data.sessionId}`).emit('segment.created', segment);

      this.logger.log(`Segment ${segment.id} created for session ${data.sessionId}`);
      return { success: true, segment };
    } catch (error) {
      this.logger.error(`Failed to create segment: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Update a segment.
   */
  @SubscribeMessage('segment.update')
  async handleUpdateSegment(
    @MessageBody() data: {
      segmentId: string;
      sessionId: string;
      name?: string;
      description?: string;
      color?: string;
      matchCriteria?: {
        field: string;
        operator: 'equals' | 'contains' | 'startsWith' | 'in' | 'notEquals';
        value: string | string[];
      };
      priority?: number;
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    try {
      const segment = await this.segmentService.updateSegment(data.segmentId, data);

      this.server.to(`session:${data.sessionId}`).emit('segment.updated', segment);

      this.logger.log(`Segment ${data.segmentId} updated`);
      return { success: true, segment };
    } catch (error) {
      this.logger.error(`Failed to update segment: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Delete a segment.
   */
  @SubscribeMessage('segment.delete')
  async handleDeleteSegment(
    @MessageBody() data: { segmentId: string; sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    try {
      await this.segmentService.deleteSegment(data.segmentId);

      this.server.to(`session:${data.sessionId}`).emit('segment.deleted', {
        segmentId: data.segmentId,
      });

      this.logger.log(`Segment ${data.segmentId} deleted`);
      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to delete segment: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * List all segments for a session.
   */
  @SubscribeMessage('segment.list')
  async handleListSegments(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    try {
      const segments = await this.segmentService.getSegmentsBySession(data.sessionId);
      return { success: true, segments };
    } catch (error) {
      this.logger.error(`Failed to list segments: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Add a member to a segment manually.
   */
  @SubscribeMessage('segment.member.add')
  async handleAddSegmentMember(
    @MessageBody() data: { segmentId: string; userId: string; sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    try {
      const member = await this.segmentService.addMemberToSegment(
        data.segmentId,
        data.userId,
        false, // manually added
      );

      this.server.to(`session:${data.sessionId}`).emit('segment.member.added', {
        segmentId: data.segmentId,
        userId: data.userId,
      });

      return { success: true, member };
    } catch (error) {
      this.logger.error(`Failed to add segment member: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Remove a member from a segment.
   */
  @SubscribeMessage('segment.member.remove')
  async handleRemoveSegmentMember(
    @MessageBody() data: { segmentId: string; userId: string; sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    try {
      await this.segmentService.removeMemberFromSegment(data.segmentId, data.userId);

      this.server.to(`session:${data.sessionId}`).emit('segment.member.removed', {
        segmentId: data.segmentId,
        userId: data.userId,
      });

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to remove segment member: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Create an assignment rule (segment -> room mapping).
   */
  @SubscribeMessage('segment.rule.create')
  async handleCreateSegmentRule(
    @MessageBody() data: {
      segmentId: string;
      roomId: string;
      sessionId: string;
      maxFromSegment?: number;
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    try {
      const rule = await this.segmentService.createAssignmentRule({
        segmentId: data.segmentId,
        roomId: data.roomId,
        maxFromSegment: data.maxFromSegment,
      });

      this.server.to(`session:${data.sessionId}`).emit('segment.rule.created', rule);

      this.logger.log(`Assignment rule created: segment ${data.segmentId} -> room ${data.roomId}`);
      return { success: true, rule };
    } catch (error) {
      this.logger.error(`Failed to create assignment rule: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Delete an assignment rule.
   */
  @SubscribeMessage('segment.rule.delete')
  async handleDeleteSegmentRule(
    @MessageBody() data: { segmentId: string; roomId: string; sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    try {
      await this.segmentService.deleteAssignmentRule(data.segmentId, data.roomId);

      this.server.to(`session:${data.sessionId}`).emit('segment.rule.deleted', {
        segmentId: data.segmentId,
        roomId: data.roomId,
      });

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to delete assignment rule: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Auto-assign attendees to segments based on their registration data.
   */
  @SubscribeMessage('segment.auto-assign')
  async handleAutoAssignSegments(
    @MessageBody() data: {
      sessionId: string;
      attendees: Array<{
        userId: string;
        registrationData?: Record<string, unknown>;
      }>;
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    try {
      const assignments = await this.segmentService.autoAssignToSegments(
        data.sessionId,
        data.attendees,
      );

      this.server.to(`session:${data.sessionId}`).emit('segment.auto-assigned', {
        assignmentCount: assignments.length,
        assignments,
      });

      this.logger.log(`Auto-assigned ${assignments.length} attendees to segments`);
      return { success: true, assignments };
    } catch (error) {
      this.logger.error(`Failed to auto-assign segments: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Compute room assignments based on segment rules.
   */
  @SubscribeMessage('segment.assignment.compute')
  async handleComputeAssignments(
    @MessageBody() data: { sessionId: string; eventId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to manage segments' };
    }

    // Rate limit check - this is an expensive operation
    if (!this.checkRateLimit(user.sub, 'assignment.compute')) {
      this.logger.warn(`Rate limit exceeded for user ${user.sub} on assignment.compute`);
      return { success: false, error: 'Too many requests. Please try again later.' };
    }

    try {
      const result = await this.segmentService.computeRoomAssignments(
        data.sessionId,
        data.eventId,
      );

      this.server.to(`session:${data.sessionId}`).emit('segment.assignments.computed', {
        created: result.created,
        errors: result.errors,
      });

      this.logger.log(`Computed ${result.created} room assignments for session ${data.sessionId}`);
      return { success: true, ...result };
    } catch (error) {
      this.logger.error(`Failed to compute assignments: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get a user's room assignment for a session.
   */
  @SubscribeMessage('segment.assignment.get')
  async handleGetAssignment(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const assignment = await this.segmentService.getUserAssignment(
        data.sessionId,
        user.sub,
      );

      return { success: true, assignment };
    } catch (error) {
      this.logger.error(`Failed to get assignment: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get all assignments for a session (organizer only).
   */
  @SubscribeMessage('segment.assignment.list')
  async handleListAssignments(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to view all assignments' };
    }

    try {
      const assignments = await this.segmentService.getSessionAssignments(data.sessionId);
      return { success: true, assignments };
    } catch (error) {
      this.logger.error(`Failed to list assignments: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Notify all attendees about their room assignments.
   */
  @SubscribeMessage('segment.assignment.notify')
  async handleNotifyAssignments(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to notify assignments' };
    }

    // Rate limit check
    if (!this.checkRateLimit(user.sub, 'assignment.notify')) {
      this.logger.warn(`Rate limit exceeded for user ${user.sub} on assignment.notify`);
      return { success: false, error: 'Too many requests. Please try again later.' };
    }

    try {
      const result = await this.segmentService.notifyAllAssignments(data.sessionId);

      // Get all assignments to notify users individually
      const assignments = await this.segmentService.getSessionAssignments(data.sessionId);

      // Emit to session room for organizer UI update
      this.server.to(`session:${data.sessionId}`).emit('segment.assignments.notified', {
        count: result.count,
      });

      // Emit individual assignment notifications to each user's socket
      for (const assignment of assignments) {
        // Users join a personal room on connection, e.g., user:userId
        this.server.to(`user:${assignment.userId}`).emit('breakout.assignment.received', {
          sessionId: data.sessionId,
          assignment: {
            roomId: assignment.roomId,
            roomName: assignment.room.name,
            status: assignment.status,
          },
        });
      }

      this.logger.log(`Notified ${result.count} assignments for session ${data.sessionId}`);
      return { success: true, notified: result.count };
    } catch (error) {
      this.logger.error(`Failed to notify assignments: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Clear all assignments for a session (for re-assignment).
   */
  @SubscribeMessage('segment.assignment.clear')
  async handleClearAssignments(
    @MessageBody() data: { sessionId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    if (!user.permissions?.includes('breakout:manage')) {
      return { success: false, error: 'You do not have permission to clear assignments' };
    }

    try {
      const result = await this.segmentService.clearSessionAssignments(data.sessionId);

      this.server.to(`session:${data.sessionId}`).emit('segment.assignments.cleared', {
        count: result.count,
      });

      this.logger.log(`Cleared ${result.count} assignments for session ${data.sessionId}`);
      return { success: true, cleared: result.count };
    } catch (error) {
      this.logger.error(`Failed to clear assignments: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Update a user's assignment status (confirm/decline).
   */
  @SubscribeMessage('segment.assignment.respond')
  async handleRespondToAssignment(
    @MessageBody() data: { sessionId: string; status: 'CONFIRMED' | 'DECLINED' },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const status = data.status === 'CONFIRMED'
        ? AssignmentStatus.CONFIRMED
        : AssignmentStatus.DECLINED;

      const assignment = await this.segmentService.updateAssignmentStatus(
        data.sessionId,
        user.sub,
        status,
      );

      this.server.to(`session:${data.sessionId}`).emit('segment.assignment.responded', {
        userId: user.sub,
        roomId: assignment.roomId,
        status: assignment.status,
      });

      return { success: true, assignment };
    } catch (error) {
      this.logger.error(`Failed to respond to assignment: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // User Profile for Segmentation
  // ==========================================

  /**
   * Update user profile for segmentation matching.
   * These optional fields help the system auto-assign users to breakout rooms.
   */
  @SubscribeMessage('profile.update')
  async handleUpdateProfile(
    @MessageBody() data: {
      currentRole?: string;
      company?: string;
      industry?: string;
      experienceLevel?: string;
      interests?: string[];
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const profile = await this.segmentService.updateUserProfile(user.sub, data);

      this.logger.log(`Profile updated for user ${user.sub}`);
      return { success: true, profile };
    } catch (error) {
      this.logger.error(`Failed to update profile: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get current user's profile for segmentation
   */
  @SubscribeMessage('profile.get')
  async handleGetProfile(
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const profile = await this.segmentService.getUserProfile(user.sub);
      return { success: true, profile };
    } catch (error) {
      this.logger.error(`Failed to get profile: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // Timer Helper Methods
  // ==========================================

  /**
   * Acquire a lock for timer operations to prevent race conditions.
   * Uses a simple spinlock with immediate return if already locked.
   */
  private acquireTimerLock(roomId: string): boolean {
    if (this.timerLocks.has(roomId)) {
      return false;
    }
    this.timerLocks.add(roomId);
    return true;
  }

  /**
   * Release the timer lock for a room.
   */
  private releaseTimerLock(roomId: string): void {
    this.timerLocks.delete(roomId);
  }

  /**
   * Start the countdown timer for a room.
   * Fixed: Tracks all timeouts (main + warnings) to prevent memory leaks.
   * Fixed: Uses lock to prevent race conditions.
   */
  private startRoomTimer(roomId: string, sessionId: string, durationMinutes: number) {
    // Acquire lock to prevent race conditions
    if (!this.acquireTimerLock(roomId)) {
      this.logger.warn(`Timer operation in progress for room ${roomId}, skipping`);
      return;
    }

    try {
      // Clear any existing timers
      this.cancelRoomTimerInternal(roomId);

      const durationMs = durationMinutes * 60 * 1000;
      const warningTimes = [5 * 60 * 1000, 1 * 60 * 1000]; // 5 min and 1 min warnings
      const breakoutRoom = `breakout:${roomId}`;
      const warningTimeouts: NodeJS.Timeout[] = [];

      // Set up warning timers
      warningTimes.forEach((warningMs) => {
        if (durationMs > warningMs) {
          const warningTimeout = setTimeout(() => {
            const minutesRemaining = Math.round(warningMs / 60000);

            try {
              this.server.to(breakoutRoom).emit('breakout.timer.warning', {
                roomId,
                minutesRemaining,
                message: `${minutesRemaining} minute${minutesRemaining > 1 ? 's' : ''} remaining`,
              });

              // Set CLOSING status at 1 minute warning
              if (minutesRemaining === 1) {
                this.breakoutService.setRoomClosing(roomId)
                  .then(() => {
                    this.logger.log(`Room ${roomId} status set to CLOSING`);
                  })
                  .catch((err) => {
                    this.logger.error(`Failed to set room ${roomId} to closing: ${err.message}`);
                    // Emit error to room so users know something went wrong
                    this.server.to(breakoutRoom).emit('breakout.room.error', {
                      roomId,
                      error: 'Failed to update room status',
                    });
                  });
              }
            } catch (err) {
              this.logger.error(`Error in warning timer for room ${roomId}: ${getErrorMessage(err)}`);
            }
          }, durationMs - warningMs);

          warningTimeouts.push(warningTimeout);
        }
      });

      // Set up end timer
      const endTimeout = setTimeout(() => {
        // Use a separate async function to handle the close operation
        this.handleTimerClose(roomId, sessionId, breakoutRoom);
      }, durationMs);

      // Store all timers (main + warnings) for proper cleanup
      this.roomTimers.set(roomId, { main: endTimeout, warnings: warningTimeouts });

      this.logger.log(`Timer started for room ${roomId}: ${durationMinutes} minutes`);
    } finally {
      this.releaseTimerLock(roomId);
    }
  }

  /**
   * Handle the room closure when timer expires.
   * Separated from setTimeout callback for better error handling.
   */
  private async handleTimerClose(roomId: string, sessionId: string, breakoutRoom: string): Promise<void> {
    try {
      // Clean up timer tracking first
      this.roomTimers.delete(roomId);

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

      // Notify room participants about the error
      try {
        this.server.to(breakoutRoom).emit('breakout.room.error', {
          roomId,
          error: 'Timer-based closure failed. Please close the room manually.',
        });
      } catch (notifyError) {
        this.logger.error(`Failed to notify room ${roomId} about close error: ${getErrorMessage(notifyError)}`);
      }
    }
  }

  /**
   * Cancel the timer for a room (internal - no lock).
   * Clears both main and warning timers.
   */
  private cancelRoomTimerInternal(roomId: string): void {
    const timers = this.roomTimers.get(roomId);
    if (timers) {
      // Clear main timer
      clearTimeout(timers.main);

      // Clear all warning timers
      timers.warnings.forEach((timeout) => clearTimeout(timeout));

      this.roomTimers.delete(roomId);
      this.logger.log(`Timers cancelled for room ${roomId}`);
    }
  }

  /**
   * Cancel the timer for a room (public - with lock).
   */
  private cancelRoomTimer(roomId: string): void {
    // Acquire lock to prevent race conditions
    if (!this.acquireTimerLock(roomId)) {
      this.logger.warn(`Timer operation in progress for room ${roomId}, waiting...`);
      // Retry after a short delay
      setTimeout(() => this.cancelRoomTimer(roomId), 50);
      return;
    }

    try {
      this.cancelRoomTimerInternal(roomId);
    } finally {
      this.releaseTimerLock(roomId);
    }
  }
}
