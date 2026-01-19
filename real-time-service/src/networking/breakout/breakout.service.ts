// src/networking/breakout/breakout.service.ts
import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { DailyService } from './daily.service';
import { CreateRoomDto } from './dto/create-room.dto';
import { Prisma, BreakoutRoomStatus } from '@prisma/client';

// Type for room with participant count
export interface BreakoutRoomWithCount {
  id: string;
  name: string;
  topic: string | null;
  sessionId: string;
  eventId: string;
  maxParticipants: number;
  durationMinutes: number;
  autoAssign: boolean;
  status: BreakoutRoomStatus;
  startedAt: Date | null;
  endedAt: Date | null;
  createdAt: Date;
  videoRoomId: string | null;
  videoRoomUrl: string | null;
  creator: {
    id: string;
    firstName: string | null;
    lastName: string | null;
  };
  facilitator: {
    id: string;
    firstName: string | null;
    lastName: string | null;
  } | null;
  _count: {
    participants: number;
  };
}

@Injectable()
export class BreakoutService {
  private readonly logger = new Logger(BreakoutService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly idempotencyService: IdempotencyService,
    private readonly dailyService: DailyService,
  ) {}

  /**
   * Creates a new breakout room for a session.
   */
  async createRoom(creatorId: string, dto: CreateRoomDto): Promise<BreakoutRoomWithCount> {
    // Check idempotency if key provided
    if (dto.idempotencyKey) {
      const canProceed = await this.idempotencyService.checkAndSet(dto.idempotencyKey);
      if (!canProceed) {
        throw new ConflictException('This breakout room has already been created.');
      }
    }

    this.logger.log(
      `User ${creatorId} creating breakout room "${dto.name}" for session ${dto.sessionId}`,
    );

    const room = await this.prisma.breakoutRoom.create({
      data: {
        sessionId: dto.sessionId,
        eventId: dto.eventId,
        name: dto.name,
        topic: dto.topic,
        maxParticipants: dto.maxParticipants || 8,
        durationMinutes: dto.durationMinutes || 15,
        autoAssign: dto.autoAssign || false,
        creatorId,
        facilitatorId: dto.facilitatorId || creatorId,
        status: 'WAITING',
      },
      include: {
        creator: { select: { id: true, firstName: true, lastName: true } },
        facilitator: { select: { id: true, firstName: true, lastName: true } },
        _count: { select: { participants: true } },
      },
    });

    return room;
  }

  /**
   * Gets all active breakout rooms for a session.
   * Includes active participants (those who haven't left) so frontend can determine user's room.
   */
  async getRoomsForSession(sessionId: string) {
    const rooms = await this.prisma.breakoutRoom.findMany({
      where: {
        sessionId,
        status: { not: 'CLOSED' },
      },
      include: {
        creator: { select: { id: true, firstName: true, lastName: true } },
        facilitator: { select: { id: true, firstName: true, lastName: true } },
        participants: {
          where: { leftAt: null }, // Only include active participants
          select: {
            userId: true,
            role: true,
            joinedAt: true,
            leftAt: true,
          },
        },
      },
      orderBy: { createdAt: 'asc' },
    });

    // Transform to include correct active participant count
    return rooms.map((room) => ({
      ...room,
      _count: {
        participants: room.participants.length, // Count only active participants
      },
    }));
  }

  /**
   * Gets a single breakout room by ID with participants.
   * Returns only active participants (those who haven't left).
   */
  async getRoomWithParticipants(roomId: string) {
    const room = await this.prisma.breakoutRoom.findUnique({
      where: { id: roomId },
      include: {
        creator: { select: { id: true, firstName: true, lastName: true } },
        facilitator: { select: { id: true, firstName: true, lastName: true } },
        participants: {
          where: { leftAt: null }, // Only active participants
          include: {
            user: { select: { id: true, firstName: true, lastName: true } },
          },
          orderBy: { joinedAt: 'asc' },
        },
      },
    });

    if (!room) return null;

    // Return with correct active participant count
    return {
      ...room,
      _count: {
        participants: room.participants.length,
      },
    };
  }

  /**
   * Adds a user to a breakout room.
   */
  async joinRoom(userId: string, roomId: string) {
    const room = await this.prisma.breakoutRoom.findUnique({
      where: { id: roomId },
      include: { _count: { select: { participants: true } } },
    });

    if (!room) {
      throw new NotFoundException('Breakout room not found');
    }

    if (room.status === 'CLOSED') {
      throw new BadRequestException('This breakout room has been closed');
    }

    if (room._count.participants >= room.maxParticipants) {
      throw new BadRequestException('This breakout room is full');
    }

    // Check if user is already in this room
    const existingParticipation = await this.prisma.breakoutParticipant.findUnique({
      where: { userId_roomId: { userId, roomId } },
    });

    if (existingParticipation) {
      throw new ConflictException('You are already in this breakout room');
    }

    // Check if user is in another room for the same session
    const otherRoomParticipation = await this.prisma.breakoutParticipant.findFirst({
      where: {
        userId,
        leftAt: null,
        room: {
          sessionId: room.sessionId,
          status: { not: 'CLOSED' },
          id: { not: roomId },
        },
      },
      include: { room: true },
    });

    if (otherRoomParticipation) {
      throw new BadRequestException(
        `You are already in breakout room "${otherRoomParticipation.room.name}". Please leave that room first.`,
      );
    }

    // Determine role - facilitator if they're the designated facilitator
    const role = room.facilitatorId === userId ? 'FACILITATOR' : 'PARTICIPANT';

    await this.prisma.breakoutParticipant.create({
      data: {
        userId,
        roomId,
        role,
      },
    });

    this.logger.log(`User ${userId} joined breakout room ${roomId} as ${role}`);

    return this.getRoomWithParticipants(roomId);
  }

  /**
   * Removes a user from a breakout room.
   */
  async leaveRoom(userId: string, roomId: string) {
    const participation = await this.prisma.breakoutParticipant.findUnique({
      where: { userId_roomId: { userId, roomId } },
    });

    if (!participation) {
      throw new NotFoundException('You are not in this breakout room');
    }

    // Update with leftAt timestamp rather than deleting (for analytics)
    await this.prisma.breakoutParticipant.update({
      where: { userId_roomId: { userId, roomId } },
      data: { leftAt: new Date() },
    });

    this.logger.log(`User ${userId} left breakout room ${roomId}`);

    return this.getRoomWithParticipants(roomId);
  }

  /**
   * Checks if a user is currently an active participant in a breakout room.
   */
  async isUserInRoom(roomId: string, userId: string): Promise<boolean> {
    const participation = await this.prisma.breakoutParticipant.findUnique({
      where: { userId_roomId: { userId, roomId } },
    });

    // User is in room if they have a participation record and haven't left
    return participation !== null && participation.leftAt === null;
  }

  /**
   * Starts the timer for a breakout room and creates a Daily video room.
   */
  async startRoom(roomId: string, userId: string, userPermissions: string[]) {
    const room = await this.prisma.breakoutRoom.findUnique({
      where: { id: roomId },
    });

    if (!room) {
      throw new NotFoundException('Breakout room not found');
    }

    // Check permissions - must be facilitator or have breakout:manage permission
    const isFacilitator = room.facilitatorId === userId || room.creatorId === userId;
    const hasManagePermission = userPermissions.includes('breakout:manage');

    if (!isFacilitator && !hasManagePermission) {
      throw new ForbiddenException('You do not have permission to start this breakout room');
    }

    if (room.status !== 'WAITING') {
      throw new BadRequestException('This breakout room has already started or closed');
    }

    // Create Daily video room
    const dailyRoom = await this.dailyService.createRoom({
      name: room.name,
      maxParticipants: room.maxParticipants,
      expiryMinutes: room.durationMinutes + 10, // Add buffer time
    });

    const updateData: Prisma.BreakoutRoomUpdateInput = {
      status: 'ACTIVE',
      startedAt: new Date(),
    };

    // Store video room info if Daily room was created successfully
    if (dailyRoom) {
      updateData.videoRoomId = dailyRoom.name;
      updateData.videoRoomUrl = dailyRoom.url;
    }

    const updatedRoom = await this.prisma.breakoutRoom.update({
      where: { id: roomId },
      data: updateData,
      include: {
        creator: { select: { id: true, firstName: true, lastName: true } },
        facilitator: { select: { id: true, firstName: true, lastName: true } },
        _count: { select: { participants: true } },
      },
    });

    this.logger.log(`Breakout room ${roomId} started by ${userId}${dailyRoom ? ` with Daily room ${dailyRoom.name}` : ''}`);

    return updatedRoom;
  }

  /**
   * Gets a video room URL with a meeting token for a user.
   * Organizers with breakout:manage permission can join without being a participant.
   */
  async getVideoRoomUrl(
    roomId: string,
    userId: string,
    userName: string,
    userPermissions: string[] = [],
  ): Promise<{ url: string; token: string } | null> {
    const room = await this.prisma.breakoutRoom.findUnique({
      where: { id: roomId },
    });

    if (!room || !room.videoRoomId || !room.videoRoomUrl) {
      return null;
    }

    if (room.status !== 'ACTIVE') {
      return null;
    }

    // Check if user is an organizer with manage permission
    const hasManagePermission = userPermissions.includes('breakout:manage');
    const isCreatorOrFacilitator = room.facilitatorId === userId || room.creatorId === userId;

    // Check if user is a participant (only required if not an organizer)
    if (!hasManagePermission && !isCreatorOrFacilitator) {
      const participation = await this.prisma.breakoutParticipant.findUnique({
        where: { userId_roomId: { userId, roomId } },
      });

      if (!participation || participation.leftAt) {
        return null;
      }
    }

    // Create meeting token - organizers get owner privileges
    const isOwner = hasManagePermission || isCreatorOrFacilitator;
    const token = await this.dailyService.createMeetingToken({
      roomName: room.videoRoomId,
      userName,
      userId,
      isOwner,
      expiryMinutes: room.durationMinutes + 10,
    });

    if (!token) {
      return null;
    }

    return {
      url: room.videoRoomUrl,
      token,
    };
  }

  /**
   * Closes a breakout room and deletes the Daily video room.
   */
  async closeRoom(roomId: string, userId: string, userPermissions: string[]) {
    const room = await this.prisma.breakoutRoom.findUnique({
      where: { id: roomId },
    });

    if (!room) {
      throw new NotFoundException('Breakout room not found');
    }

    // Check permissions - must be facilitator, creator, or have breakout:manage permission
    const isFacilitator = room.facilitatorId === userId || room.creatorId === userId;
    const hasManagePermission = userPermissions.includes('breakout:manage');

    if (!isFacilitator && !hasManagePermission) {
      throw new ForbiddenException('You do not have permission to close this breakout room');
    }

    if (room.status === 'CLOSED') {
      throw new BadRequestException('This breakout room is already closed');
    }

    // Delete Daily video room if it exists
    if (room.videoRoomId) {
      await this.dailyService.deleteRoom(room.videoRoomId);
    }

    // Update all participants to have leftAt set
    await this.prisma.breakoutParticipant.updateMany({
      where: { roomId, leftAt: null },
      data: { leftAt: new Date() },
    });

    const closedRoom = await this.prisma.breakoutRoom.update({
      where: { id: roomId },
      data: {
        status: 'CLOSED',
        endedAt: new Date(),
      },
      include: {
        creator: { select: { id: true, firstName: true, lastName: true } },
        facilitator: { select: { id: true, firstName: true, lastName: true } },
        _count: { select: { participants: true } },
      },
    });

    this.logger.log(`Breakout room ${roomId} closed by ${userId}`);

    return closedRoom;
  }

  /**
   * Sets room status to CLOSING (warning state).
   */
  async setRoomClosing(roomId: string) {
    return this.prisma.breakoutRoom.update({
      where: { id: roomId },
      data: { status: 'CLOSING' },
    });
  }

  /**
   * Get all active participants across all rooms in a session.
   */
  async getSessionParticipants(sessionId: string) {
    return this.prisma.breakoutParticipant.findMany({
      where: {
        leftAt: null,
        room: {
          sessionId,
          status: { not: 'CLOSED' },
        },
      },
      include: {
        user: { select: { id: true, firstName: true, lastName: true } },
        room: { select: { id: true, name: true } },
      },
    });
  }

  /**
   * Close all rooms for a session (recall all).
   */
  async closeAllRooms(sessionId: string, userId: string, userPermissions: string[]) {
    const hasManagePermission = userPermissions.includes('breakout:manage');

    if (!hasManagePermission) {
      throw new ForbiddenException('You do not have permission to close all breakout rooms');
    }

    const rooms = await this.prisma.breakoutRoom.findMany({
      where: { sessionId, status: { not: 'CLOSED' } },
    });

    // Close all rooms
    await this.prisma.$transaction([
      // Update all participants
      this.prisma.breakoutParticipant.updateMany({
        where: {
          leftAt: null,
          room: { sessionId, status: { not: 'CLOSED' } },
        },
        data: { leftAt: new Date() },
      }),
      // Close all rooms
      this.prisma.breakoutRoom.updateMany({
        where: { sessionId, status: { not: 'CLOSED' } },
        data: { status: 'CLOSED', endedAt: new Date() },
      }),
    ]);

    this.logger.log(`All breakout rooms for session ${sessionId} closed by ${userId}`);

    return rooms.map((r) => r.id);
  }
}
