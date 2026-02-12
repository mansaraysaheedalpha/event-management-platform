// src/expo/expo.service.ts
import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  Injectable,
  Logger,
  NotFoundException,
} from '@nestjs/common';
import { PrismaService } from 'src/prisma.service';
import { DailyService } from 'src/networking/breakout/daily.service';
import {
  BoothVisitorStatus,
  BoothVideoSessionStatus,
  BoothQueueStatus,
  StaffPresenceStatus,
  Prisma,
  BoothQueueEntry,
  BoothVisit,
} from '@prisma/client';

export interface ExpoBoothWithCount {
  id: string;
  name: string;
  tagline: string | null;
  description: string | null;
  tier: string;
  boothNumber: string;
  logoUrl: string | null;
  bannerUrl: string | null;
  videoUrl: string | null;
  resources: unknown;
  ctaButtons: unknown;
  chatEnabled: boolean;
  videoEnabled: boolean;
  maxVisitors: number | null;
  category: string | null;
  sponsorId: string;
  _count: {
    visits: number;
    queueEntries?: number;
  };
  staffPresence: Array<{
    staffId: string;
    staffName: string;
    staffAvatarUrl: string | null;
    status: StaffPresenceStatus;
  }>;
}

export interface EnterBoothResult {
  status: 'entered' | 'queued';
  visit?: BoothVisit;
  queued?: BoothQueueEntry;
}

export interface LeaveBoothResult {
  visit: BoothVisit | null;
  admittedEntry: BoothQueueEntry | null;
}

export interface CloseVisitResult {
  boothId: string;
  admittedEntry: BoothQueueEntry | null;
}

@Injectable()
export class ExpoService {
  private readonly logger = new Logger(ExpoService.name);

  constructor(
    private readonly prisma: PrismaService,
    private readonly dailyService: DailyService,
  ) {}

  /**
   * Gets the expo hall for an event.
   */
  async getExpoHall(eventId: string) {
    const hall = await this.prisma.expoHall.findUnique({
      where: { eventId },
      include: {
        booths: {
          where: {
            /* isActive: true */
          }, // All booths for now
          include: {
            staffPresence: {
              where: { status: { not: 'OFFLINE' } },
            },
            _count: {
              select: {
                visits: {
                  where: { exitedAt: null },
                },
                queueEntries: {
                  where: { status: 'WAITING' },
                },
              },
            },
          },
          orderBy: [{ tier: 'asc' }, { displayOrder: 'asc' }],
        },
      },
    });

    if (!hall) {
      throw new NotFoundException('Expo hall not found for this event');
    }

    return hall;
  }

  /**
   * Gets the expo hall for an event, returns null if not found.
   */
  async getExpoHallSafe(eventId: string) {
    return this.prisma.expoHall.findUnique({
      where: { eventId },
      include: {
        booths: {
          include: {
            staffPresence: {
              where: { status: { not: 'OFFLINE' } },
            },
            _count: {
              select: {
                visits: { where: { exitedAt: null } },
                queueEntries: { where: { status: 'WAITING' } },
              },
            },
          },
          orderBy: [{ tier: 'asc' }, { displayOrder: 'asc' }],
        },
        _count: {
          select: { booths: true },
        },
      },
    });
  }

  /**
   * Gets an expo hall by ID.
   */
  async getExpoHallById(hallId: string) {
    return this.prisma.expoHall.findUnique({
      where: { id: hallId },
      include: {
        booths: {
          include: {
            staffPresence: {
              where: { status: { not: 'OFFLINE' } },
            },
            _count: {
              select: {
                visits: { where: { exitedAt: null } },
                queueEntries: { where: { status: 'WAITING' } },
              },
            },
          },
          orderBy: [{ tier: 'asc' }, { displayOrder: 'asc' }],
        },
        _count: {
          select: { booths: true },
        },
      },
    });
  }

  /**
   * Creates an expo hall for an event.
   */
  async createExpoHall(
    eventId: string,
    organizationId: string,
    data: {
      name: string;
      description?: string;
      categories?: string[];
      welcomeMessage?: string;
    },
  ) {
    // Check if hall already exists
    const existing = await this.prisma.expoHall.findUnique({
      where: { eventId },
    });

    if (existing) {
      throw new ConflictException('Expo hall already exists for this event');
    }

    const hall = await this.prisma.expoHall.create({
      data: {
        eventId,
        organizationId,
        name: data.name,
        description: data.description,
        categories: data.categories || [],
        welcomeMessage: data.welcomeMessage,
        isActive: true,
      },
      include: {
        booths: true,
        _count: { select: { booths: true } },
      },
    });

    this.logger.log(`Created expo hall ${hall.id} for event ${eventId}`);
    return hall;
  }

  /**
   * Updates an expo hall.
   */
  async updateExpoHall(
    hallId: string,
    data: {
      name?: string;
      description?: string;
      categories?: string[];
      welcomeMessage?: string;
      isActive?: boolean;
    },
  ) {
    const hall = await this.prisma.expoHall.update({
      where: { id: hallId },
      data,
      include: {
        booths: true,
        _count: { select: { booths: true } },
      },
    });

    this.logger.log(`Updated expo hall ${hallId}`);
    return hall;
  }

  /**
   * Creates a booth in an expo hall.
   */
  async createBooth(
    hallId: string,
    organizationId: string,
    data: {
      name: string;
      tagline?: string;
      description?: string;
      tier?: 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP';
      logoUrl?: string;
      bannerUrl?: string;
      videoUrl?: string;
      category?: string;
      sponsorId?: string;
      maxVisitors?: number;
    },
  ) {
    // Generate booth number based on existing count
    const existingCount = await this.prisma.expoBooth.count({
      where: { expoHallId: hallId },
    });
    const boothNumber = `B${String(existingCount + 1).padStart(3, '0')}`;

    const booth = await this.prisma.expoBooth.create({
      data: {
        expoHallId: hallId,
        name: data.name,
        tagline: data.tagline,
        description: data.description,
        tier: data.tier || 'BRONZE',
        logoUrl: data.logoUrl,
        bannerUrl: data.bannerUrl,
        videoUrl: data.videoUrl,
        category: data.category,
        sponsorId: data.sponsorId || `test-sponsor-${Date.now()}`,
        organizationId,
        boothNumber,
        resources: [],
        ctaButtons: [],
        staffIds: [],
        chatEnabled: true,
        videoEnabled: true,
        maxVisitors: data.maxVisitors ?? null,
      },
      include: {
        _count: { select: { visits: true } },
      },
    });

    this.logger.log(`Created booth ${booth.id} in hall ${hallId}`);
    return booth;
  }

  /**
   * Gets a single booth with details.
   */
  async getBooth(boothId: string) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
      include: {
        staffPresence: true,
        _count: {
          select: {
            visits: { where: { exitedAt: null } },
            chatMessages: true,
          },
        },
      },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    return booth;
  }

  /**
   * Gets a booth by sponsor ID.
   */
  async getBoothBySponsorId(sponsorId: string) {
    return this.prisma.expoBooth.findFirst({
      where: { sponsorId },
      include: {
        staffPresence: true,
        _count: {
          select: {
            visits: { where: { exitedAt: null } },
            chatMessages: true,
          },
        },
      },
    });
  }

  /**
   * Updates a booth's details.
   * Note: Booths don't have an isActive field - use expo hall isActive for that.
   */
  async updateBooth(
    boothId: string,
    data: {
      name?: string;
      tagline?: string;
      description?: string;
      tier?: 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP';
      logoUrl?: string;
      bannerUrl?: string;
      videoUrl?: string;
      category?: string;
      chatEnabled?: boolean;
      videoEnabled?: boolean;
      displayOrder?: number;
      maxVisitors?: number | null;
    },
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const updated = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data,
      include: {
        _count: { select: { visits: true } },
      },
    });

    this.logger.log(`Updated booth ${boothId}`);
    return updated;
  }

  /**
   * Deletes a booth.
   * This is used when a sponsor is archived since booths don't have an isActive field.
   */
  async deleteBooth(boothId: string) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    // Delete the booth (this will cascade delete related records due to schema relations)
    await this.prisma.expoBooth.delete({
      where: { id: boothId },
    });

    this.logger.log(`Deleted booth ${boothId}`);
    return { deleted: true, id: boothId };
  }

  /**
   * Records a user entering the expo hall.
   */
  async enterHall(userId: string, eventId: string) {
    this.logger.log(`User ${userId} entered expo hall for event ${eventId}`);
    return this.getExpoHall(eventId);
  }

  /**
   * Records a user entering a booth.
   * If the booth is at capacity, adds the user to the queue instead.
   */
  async enterBooth(
    userId: string,
    boothId: string,
    eventId: string,
    socketId: string,
    userName: string,
  ): Promise<EnterBoothResult> {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    // Check if user already has an active visit to this booth
    const existingVisit = await this.prisma.boothVisit.findFirst({
      where: {
        boothId,
        userId,
        exitedAt: null,
      },
    });

    if (existingVisit) {
      // Update socket ID and return existing visit
      const visit = await this.prisma.boothVisit.update({
        where: { id: existingVisit.id },
        data: { socketId },
      });
      return { status: 'entered', visit };
    }

    // Check if user is already in queue
    const existingQueue = await this.prisma.boothQueueEntry.findUnique({
      where: { boothId_userId: { boothId, userId } },
    });

    if (existingQueue && existingQueue.status === 'WAITING') {
      // Update socket and return queue info
      const updated = await this.prisma.boothQueueEntry.update({
        where: { id: existingQueue.id },
        data: { socketId },
      });
      return { status: 'queued', queued: updated };
    }

    // If user was ADMITTED, let them enter (fall through to enter logic)
    if (existingQueue && existingQueue.status === 'ADMITTED') {
      await this.prisma.boothQueueEntry.update({
        where: { id: existingQueue.id },
        data: { status: 'ENTERED', enteredAt: new Date() },
      });
    }

    // Check capacity
    if (booth.maxVisitors) {
      const currentCount = await this.getBoothVisitorCount(boothId);
      if (currentCount >= booth.maxVisitors && existingQueue?.status !== 'ADMITTED') {
        // Booth is full -- add to queue
        const queueEntry = await this.addToQueue(
          userId,
          userName,
          boothId,
          eventId,
          socketId,
        );
        return { status: 'queued', queued: queueEntry };
      }
    }

    // Exit any other active booth visits for this user
    await this.prisma.boothVisit.updateMany({
      where: {
        userId,
        exitedAt: null,
      },
      data: {
        exitedAt: new Date(),
      },
    });

    // Clean up any stale queue entry for this user
    await this.prisma.boothQueueEntry.deleteMany({
      where: { boothId, userId },
    });

    // Create new visit
    const visit = await this.prisma.boothVisit.create({
      data: {
        boothId,
        userId,
        eventId,
        socketId,
        status: 'BROWSING',
      },
    });

    this.logger.log(`User ${userId} entered booth ${boothId}`);

    return { status: 'entered', visit };
  }

  /**
   * Gets or creates a visit record for a user/booth combination.
   * This is used when the in-memory visit tracking is lost (e.g., after server restart or socket reconnect).
   */
  async getOrCreateVisit(userId: string, boothId: string, socketId: string) {
    // First, check for an existing active visit
    const existingVisit = await this.prisma.boothVisit.findFirst({
      where: {
        boothId,
        userId,
        exitedAt: null,
      },
    });

    if (existingVisit) {
      // Update socket ID and return existing visit
      return this.prisma.boothVisit.update({
        where: { id: existingVisit.id },
        data: { socketId },
      });
    }

    // Get the booth to find the event ID
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
      include: { expoHall: true },
    });

    if (!booth || !booth.expoHall) {
      this.logger.warn(`Cannot create visit: booth ${boothId} not found`);
      return null;
    }

    // Create a new visit
    const visit = await this.prisma.boothVisit.create({
      data: {
        boothId,
        userId,
        eventId: booth.expoHall.eventId,
        socketId,
        status: 'BROWSING',
      },
    });

    this.logger.log(`Created visit for user ${userId} at booth ${boothId}`);
    return visit;
  }

  /**
   * Records a user leaving a booth. Admits next queued visitor if applicable.
   */
  async leaveBooth(
    userId: string,
    boothId: string,
  ): Promise<LeaveBoothResult> {
    const visit = await this.prisma.boothVisit.findFirst({
      where: {
        boothId,
        userId,
        exitedAt: null,
      },
    });

    if (!visit) {
      return { visit: null, admittedEntry: null };
    }

    // Calculate duration
    const durationSeconds = Math.floor(
      (Date.now() - visit.enteredAt.getTime()) / 1000,
    );

    const updatedVisit = await this.prisma.boothVisit.update({
      where: { id: visit.id },
      data: {
        exitedAt: new Date(),
        durationSeconds,
      },
    });

    this.logger.log(
      `User ${userId} left booth ${boothId} (duration: ${durationSeconds}s)`,
    );

    // Admit next person from queue
    const admittedEntry = await this.admitNextFromQueue(boothId);

    return { visit: updatedVisit, admittedEntry };
  }

  /**
   * Gets current visitor count for a booth.
   */
  async getBoothVisitorCount(boothId: string): Promise<number> {
    return this.prisma.boothVisit.count({
      where: {
        boothId,
        exitedAt: null,
      },
    });
  }

  // ==========================================
  // BOOTH QUEUE MANAGEMENT
  // ==========================================

  /**
   * Adds a user to the booth visitor queue.
   */
  async addToQueue(
    userId: string,
    userName: string,
    boothId: string,
    eventId: string,
    socketId: string,
  ): Promise<BoothQueueEntry> {
    // Get next position
    const lastEntry = await this.prisma.boothQueueEntry.findFirst({
      where: { boothId, status: 'WAITING' },
      orderBy: { position: 'desc' },
    });
    const nextPosition = (lastEntry?.position ?? 0) + 1;

    const entry = await this.prisma.boothQueueEntry.create({
      data: {
        boothId,
        userId,
        userName,
        eventId,
        position: nextPosition,
        status: 'WAITING',
        socketId,
      },
    });

    this.logger.log(
      `User ${userId} joined queue for booth ${boothId} at position ${nextPosition}`,
    );

    return entry;
  }

  /**
   * Returns the queue count (WAITING entries) for a booth.
   */
  async getBoothQueueCount(boothId: string): Promise<number> {
    return this.prisma.boothQueueEntry.count({
      where: { boothId, status: 'WAITING' },
    });
  }

  /**
   * Gets a user's position in the queue (1-based). Returns null if not in queue.
   */
  async getQueuePosition(
    boothId: string,
    userId: string,
  ): Promise<number | null> {
    const entry = await this.prisma.boothQueueEntry.findUnique({
      where: { boothId_userId: { boothId, userId } },
    });
    if (!entry || entry.status !== 'WAITING') return null;

    // Count how many are ahead
    const ahead = await this.prisma.boothQueueEntry.count({
      where: {
        boothId,
        status: 'WAITING',
        position: { lt: entry.position },
      },
    });
    return ahead + 1;
  }

  /**
   * Removes a user from the queue (voluntary leave).
   */
  async leaveQueue(userId: string, boothId: string): Promise<void> {
    await this.prisma.boothQueueEntry.updateMany({
      where: { boothId, userId, status: { in: ['WAITING', 'ADMITTED'] } },
      data: { status: 'LEFT', leftAt: new Date() },
    });

    this.logger.log(`User ${userId} left queue for booth ${boothId}`);
  }

  /**
   * Admits the next person in queue if capacity is available.
   * Expires stale ADMITTED entries (>60s) before checking.
   */
  async admitNextFromQueue(
    boothId: string,
  ): Promise<BoothQueueEntry | null> {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth?.maxVisitors) return null;

    // Expire stale ADMITTED entries (older than 60 seconds)
    const expiryThreshold = new Date(Date.now() - 60_000);
    await this.prisma.boothQueueEntry.updateMany({
      where: {
        boothId,
        status: 'ADMITTED',
        admittedAt: { lt: expiryThreshold },
      },
      data: { status: 'EXPIRED', leftAt: new Date() },
    });

    const currentCount = await this.getBoothVisitorCount(boothId);
    if (currentCount >= booth.maxVisitors) return null;

    // Find next waiting person
    const nextEntry = await this.prisma.boothQueueEntry.findFirst({
      where: { boothId, status: 'WAITING' },
      orderBy: { position: 'asc' },
    });

    if (!nextEntry) return null;

    // Mark as admitted
    const admitted = await this.prisma.boothQueueEntry.update({
      where: { id: nextEntry.id },
      data: { status: 'ADMITTED', admittedAt: new Date() },
    });

    this.logger.log(
      `Admitted user ${admitted.userId} from queue for booth ${boothId}`,
    );

    return admitted;
  }

  /**
   * Cleans up a queue entry when a user disconnects.
   */
  async removeFromQueueBySocket(
    socketId: string,
  ): Promise<BoothQueueEntry | null> {
    const entry = await this.prisma.boothQueueEntry.findFirst({
      where: { socketId, status: { in: ['WAITING', 'ADMITTED'] } },
    });

    if (!entry) return null;

    await this.prisma.boothQueueEntry.update({
      where: { id: entry.id },
      data: { status: 'LEFT', leftAt: new Date() },
    });

    this.logger.log(
      `Removed user ${entry.userId} from queue (disconnect) for booth ${entry.boothId}`,
    );

    return entry;
  }

  /**
   * Gets chat messages for a booth.
   */
  async getBoothChatHistory(boothId: string, limit = 50, cursor?: string) {
    const messages = await this.prisma.boothChatMessage.findMany({
      where: {
        boothId,
        isDeleted: false,
        ...(cursor ? { createdAt: { lt: new Date(cursor) } } : {}),
      },
      orderBy: { createdAt: 'desc' },
      take: limit + 1, // Take one extra to check if there are more
    });

    const hasMore = messages.length > limit;
    const items = hasMore ? messages.slice(0, -1) : messages;

    return {
      messages: items.reverse(), // Return in chronological order
      hasMore,
      nextCursor: hasMore ? items[0]?.createdAt.toISOString() : null,
    };
  }

  /**
   * Sends a chat message in a booth.
   */
  async sendBoothChat(
    userId: string,
    userName: string,
    userAvatarUrl: string | null,
    boothId: string,
    text: string,
    isStaff: boolean,
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    if (!booth.chatEnabled) {
      throw new BadRequestException('Chat is not enabled for this booth');
    }

    const message = await this.prisma.boothChatMessage.create({
      data: {
        boothId,
        senderId: userId,
        senderName: userName,
        senderAvatarUrl: userAvatarUrl,
        isStaff,
        text,
      },
    });

    this.logger.log(`Chat message sent in booth ${boothId} by ${userId}`);

    return message;
  }

  /**
   * Requests a video call with booth staff.
   */
  /**
   * Gets staff availability summary for a booth.
   */
  async getStaffAvailability(boothId: string) {
    const presence = await this.prisma.boothStaffPresence.findMany({
      where: { boothId },
    });

    const online = presence.filter((p) => p.status === 'ONLINE').length;
    const busy = presence.filter((p) => p.status === 'BUSY').length;

    return {
      total: presence.filter((p) => p.status !== 'OFFLINE').length,
      available: online,
      busy,
      allBusy: online === 0 && busy > 0,
    };
  }

  async requestVideoCall(
    userId: string,
    userName: string,
    boothId: string,
    message?: string,
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
      include: {
        staffPresence: true, // Get ALL staff, not just ONLINE
      },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    if (!booth.videoEnabled) {
      throw new BadRequestException(
        'Video calls are not enabled for this booth',
      );
    }

    // Only reject when ALL staff are OFFLINE (nobody at the booth)
    const nonOfflineStaff = booth.staffPresence.filter(
      (s) => s.status !== 'OFFLINE',
    );
    if (nonOfflineStaff.length === 0) {
      throw new BadRequestException(
        'No staff members are currently at this booth',
      );
    }

    // Check for existing pending request
    const existingRequest = await this.prisma.boothVideoSession.findFirst({
      where: {
        boothId,
        attendeeId: userId,
        status: { in: ['REQUESTED', 'ACCEPTED', 'ACTIVE'] },
      },
    });

    if (existingRequest) {
      // Auto-cleanup stale sessions to handle network disconnections
      const now = new Date();
      const sessionAge =
        now.getTime() - new Date(existingRequest.requestedAt).getTime();
      const fiveMinutes = 5 * 60 * 1000;
      const twoMinutes = 2 * 60 * 1000;

      const isStale =
        (existingRequest.status === 'ACTIVE' && sessionAge > fiveMinutes) ||
        (['REQUESTED', 'ACCEPTED'].includes(existingRequest.status) &&
          sessionAge > twoMinutes);

      if (isStale) {
        this.logger.warn(
          `Auto-ending stale video session ${existingRequest.id} for user ${userId}`,
        );
        await this.prisma.boothVideoSession.update({
          where: { id: existingRequest.id },
          data: {
            status: 'COMPLETED',
            endedAt: now,
            durationSeconds: Math.floor(sessionAge / 1000),
          },
        });
      } else {
        throw new ConflictException(
          'You already have an active or pending video request',
        );
      }
    }

    const session = await this.prisma.boothVideoSession.create({
      data: {
        boothId,
        attendeeId: userId,
        attendeeName: userName,
        status: 'REQUESTED',
        staffNotes: message,
      },
    });

    this.logger.log(`Video call requested for booth ${boothId} by ${userId}`);

    // Return session with staff availability info
    const onlineStaff = booth.staffPresence.filter(
      (s) => s.status === 'ONLINE',
    );
    const busyStaff = booth.staffPresence.filter((s) => s.status === 'BUSY');

    return {
      session,
      staffAvailability: {
        total: nonOfflineStaff.length,
        available: onlineStaff.length,
        busy: busyStaff.length,
        allBusy: onlineStaff.length === 0 && busyStaff.length > 0,
      },
    };
  }

  /**
   * Staff accepts a video call request.
   */
  async acceptVideoCall(staffId: string, staffName: string, sessionId: string) {
    const session = await this.prisma.boothVideoSession.findUnique({
      where: { id: sessionId },
      include: {
        booth: {
          include: {
            expoHall: { select: { eventId: true } },
          },
        },
      },
    });

    if (!session) {
      throw new NotFoundException('Video session not found');
    }

    if (session.status !== 'REQUESTED') {
      throw new BadRequestException('This request is no longer pending');
    }

    // Verify staff is authorized for this booth
    const staffIds = session.booth.staffIds || [];
    if (!staffIds.includes(staffId)) {
      throw new ForbiddenException('You are not authorized for this booth');
    }

    // Create Daily room for the call
    const dailyRoom = await this.dailyService.createRoom({
      name: `booth-${session.boothId}-${Date.now()}`,
      maxParticipants: 2,
      expiryMinutes: 30,
    });

    let attendeeToken: string | null = null;
    let staffToken: string | null = null;

    if (dailyRoom) {
      attendeeToken = await this.dailyService.createMeetingToken({
        roomName: dailyRoom.name,
        userName: session.attendeeName,
        userId: session.attendeeId,
        isOwner: false,
        expiryMinutes: 30,
      });

      staffToken = await this.dailyService.createMeetingToken({
        roomName: dailyRoom.name,
        userName: staffName,
        userId: staffId,
        isOwner: true,
        expiryMinutes: 30,
      });
    }

    const updatedSession = await this.prisma.boothVideoSession.update({
      where: { id: sessionId },
      data: {
        status: 'ACCEPTED',
        staffId,
        staffName,
        acceptedAt: new Date(),
        videoRoomId: dailyRoom?.name || null,
        videoRoomUrl: dailyRoom?.url || null,
        attendeeToken,
        staffToken,
      },
    });

    this.logger.log(`Video call ${sessionId} accepted by staff ${staffId}`);

    return updatedSession;
  }

  /**
   * Staff declines a video call request.
   */
  async declineVideoCall(staffId: string, sessionId: string, reason?: string) {
    const session = await this.prisma.boothVideoSession.findUnique({
      where: { id: sessionId },
      include: { booth: true },
    });

    if (!session) {
      throw new NotFoundException('Video session not found');
    }

    const boothStaffIds = session.booth.staffIds || [];
    if (!boothStaffIds.includes(staffId)) {
      throw new ForbiddenException('You are not authorized for this booth');
    }

    const updatedSession = await this.prisma.boothVideoSession.update({
      where: { id: sessionId },
      data: {
        status: 'DECLINED',
        staffId,
        endedAt: new Date(),
        staffNotes: reason,
      },
    });

    this.logger.log(`Video call ${sessionId} declined by staff ${staffId}`);

    return updatedSession;
  }

  /**
   * Starts a video call (when both parties join).
   */
  async startVideoCall(sessionId: string) {
    const session = await this.prisma.boothVideoSession.findUnique({
      where: { id: sessionId },
    });

    if (!session || session.status !== 'ACCEPTED') {
      return null;
    }

    return this.prisma.boothVideoSession.update({
      where: { id: sessionId },
      data: {
        status: 'ACTIVE',
        startedAt: new Date(),
      },
    });
  }

  /**
   * Ends a video call.
   */
  async endVideoCall(sessionId: string, endedBy: string) {
    const session = await this.prisma.boothVideoSession.findUnique({
      where: { id: sessionId },
    });

    if (!session) {
      throw new NotFoundException('Video session not found');
    }

    // Calculate duration if the call was active
    let durationSeconds = 0;
    if (session.startedAt) {
      durationSeconds = Math.floor(
        (Date.now() - session.startedAt.getTime()) / 1000,
      );
    }

    // Delete Daily room
    if (session.videoRoomId) {
      await this.dailyService.deleteRoom(session.videoRoomId);
    }

    const updatedSession = await this.prisma.boothVideoSession.update({
      where: { id: sessionId },
      data: {
        status: 'COMPLETED',
        endedAt: new Date(),
        durationSeconds,
      },
    });

    // Set staff back to ONLINE if they were BUSY
    if (session.staffId) {
      await this.prisma.boothStaffPresence.updateMany({
        where: {
          boothId: session.boothId,
          staffId: session.staffId,
          status: 'BUSY',
        },
        data: { status: 'ONLINE' },
      });
    }

    this.logger.log(
      `Video call ${sessionId} ended by ${endedBy} (duration: ${durationSeconds}s)`,
    );

    // Check for pending requests to auto-route to newly available staff
    const pendingRequests = await this.getPendingVideoRequests(
      session.boothId,
    );

    return { ...updatedSession, pendingRequests };
  }

  /**
   * Gets pending video call requests for a booth.
   */
  async getPendingVideoRequests(boothId: string) {
    return this.prisma.boothVideoSession.findMany({
      where: {
        boothId,
        status: 'REQUESTED',
      },
      orderBy: { requestedAt: 'asc' },
    });
  }

  /**
   * Updates staff presence status.
   */
  async updateStaffPresence(
    staffId: string,
    staffName: string,
    staffAvatarUrl: string | null,
    boothId: string,
    status: StaffPresenceStatus,
    socketId: string | null,
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const allowedStaffIds = booth.staffIds || [];
    if (!allowedStaffIds.includes(staffId)) {
      throw new ForbiddenException('You are not authorized for this booth');
    }

    const presence = await this.prisma.boothStaffPresence.upsert({
      where: { boothId_staffId: { boothId, staffId } },
      create: {
        boothId,
        staffId,
        staffName,
        staffAvatarUrl,
        status,
        socketId,
      },
      update: {
        status,
        socketId,
        lastSeenAt: new Date(),
      },
    });

    this.logger.log(
      `Staff ${staffId} presence updated to ${status} for booth ${boothId}`,
    );

    return presence;
  }

  /**
   * Checks if a user is booth staff.
   */
  async isBoothStaff(userId: string, boothId: string): Promise<boolean> {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
      select: { staffIds: true },
    });

    const staffIds = booth?.staffIds || [];
    return staffIds.includes(userId);
  }

  /**
   * Gets all staff presence for a booth.
   */
  async getBoothStaffPresence(boothId: string) {
    return this.prisma.boothStaffPresence.findMany({
      where: { boothId },
    });
  }

  /**
   * Handles staff socket disconnection.
   *
   * Enterprise behavior: We do NOT mark staff as OFFLINE on disconnect.
   * This allows the "live" status to persist across page refreshes and
   * temporary network interruptions. Staff remains ONLINE until they
   * explicitly click "Go Offline".
   *
   * We only clear the socketId to indicate the connection dropped,
   * and update lastSeenAt for tracking purposes.
   */
  async markStaffOffline(socketId: string) {
    await this.prisma.boothStaffPresence.updateMany({
      where: { socketId },
      data: {
        socketId: null,
        lastSeenAt: new Date(),
        // Note: status is intentionally NOT changed to OFFLINE
        // Staff must explicitly go offline via the UI
      },
    });
  }

  /**
   * Closes a user's visit when they disconnect. Admits next queued visitor.
   */
  async closeVisitBySocket(
    socketId: string,
  ): Promise<CloseVisitResult | null> {
    const visit = await this.prisma.boothVisit.findFirst({
      where: { socketId, exitedAt: null },
    });

    if (!visit) return null;

    const durationSeconds = Math.floor(
      (Date.now() - visit.enteredAt.getTime()) / 1000,
    );

    await this.prisma.boothVisit.update({
      where: { id: visit.id },
      data: {
        exitedAt: new Date(),
        durationSeconds,
      },
    });

    // Admit next person from queue
    const admittedEntry = await this.admitNextFromQueue(visit.boothId);

    return { boothId: visit.boothId, admittedEntry };
  }

  // ==========================================
  // BOOTH CONTENT MANAGEMENT
  // ==========================================

  /**
   * Adds a resource to a booth.
   */
  async addBoothResource(
    boothId: string,
    resource: {
      name: string;
      description?: string;
      type: 'PDF' | 'VIDEO' | 'IMAGE' | 'DOCUMENT' | 'LINK';
      url: string;
      thumbnailUrl?: string;
      fileSize?: number;
    },
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const resources = (booth.resources as unknown[]) || [];
    const newResource = {
      id: `res-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      ...resource,
      downloadCount: 0,
      createdAt: new Date().toISOString(),
    };

    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: {
        resources: [...resources, newResource] as Prisma.InputJsonValue,
      },
    });

    this.logger.log(`Added resource ${newResource.id} to booth ${boothId}`);
    return { booth: updatedBooth, resource: newResource };
  }

  /**
   * Updates a resource in a booth.
   */
  async updateBoothResource(
    boothId: string,
    resourceId: string,
    updates: {
      name?: string;
      description?: string;
      url?: string;
      thumbnailUrl?: string;
    },
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const resources = (booth.resources as Array<{ id: string }>) || [];
    const resourceIndex = resources.findIndex((r) => r.id === resourceId);

    if (resourceIndex === -1) {
      throw new NotFoundException('Resource not found');
    }

    resources[resourceIndex] = { ...resources[resourceIndex], ...updates };

    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: { resources: resources as Prisma.InputJsonValue },
    });

    this.logger.log(`Updated resource ${resourceId} in booth ${boothId}`);
    return { booth: updatedBooth, resource: resources[resourceIndex] };
  }

  /**
   * Removes a resource from a booth.
   */
  async removeBoothResource(boothId: string, resourceId: string) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const resources = (booth.resources as Array<{ id: string }>) || [];
    const filteredResources = resources.filter((r) => r.id !== resourceId);

    if (filteredResources.length === resources.length) {
      throw new NotFoundException('Resource not found');
    }

    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: { resources: filteredResources as Prisma.InputJsonValue },
    });

    this.logger.log(`Removed resource ${resourceId} from booth ${boothId}`);
    return updatedBooth;
  }

  /**
   * Adds a CTA button to a booth.
   */
  async addBoothCta(
    boothId: string,
    cta: {
      label: string;
      url: string;
      style?: 'primary' | 'secondary' | 'outline';
      icon?: string;
    },
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const ctaButtons = (booth.ctaButtons as unknown[]) || [];
    const newCta = {
      id: `cta-${Date.now()}-${Math.random().toString(36).substring(7)}`,
      ...cta,
      style: cta.style || 'primary',
      clickCount: 0,
      createdAt: new Date().toISOString(),
    };

    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: {
        ctaButtons: [...ctaButtons, newCta] as Prisma.InputJsonValue,
      },
    });

    this.logger.log(`Added CTA ${newCta.id} to booth ${boothId}`);
    return { booth: updatedBooth, cta: newCta };
  }

  /**
   * Updates a CTA button in a booth.
   */
  async updateBoothCta(
    boothId: string,
    ctaId: string,
    updates: {
      label?: string;
      url?: string;
      style?: 'primary' | 'secondary' | 'outline';
      icon?: string;
    },
  ) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const ctaButtons = (booth.ctaButtons as Array<{ id: string }>) || [];
    const ctaIndex = ctaButtons.findIndex((c) => c.id === ctaId);

    if (ctaIndex === -1) {
      throw new NotFoundException('CTA button not found');
    }

    ctaButtons[ctaIndex] = { ...ctaButtons[ctaIndex], ...updates };

    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: { ctaButtons: ctaButtons as Prisma.InputJsonValue },
    });

    this.logger.log(`Updated CTA ${ctaId} in booth ${boothId}`);
    return { booth: updatedBooth, cta: ctaButtons[ctaIndex] };
  }

  /**
   * Removes a CTA button from a booth.
   */
  async removeBoothCta(boothId: string, ctaId: string) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const ctaButtons = (booth.ctaButtons as Array<{ id: string }>) || [];
    const filteredCtas = ctaButtons.filter((c) => c.id !== ctaId);

    if (filteredCtas.length === ctaButtons.length) {
      throw new NotFoundException('CTA button not found');
    }

    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: { ctaButtons: filteredCtas as Prisma.InputJsonValue },
    });

    this.logger.log(`Removed CTA ${ctaId} from booth ${boothId}`);
    return updatedBooth;
  }

  /**
   * Adds a staff member to a booth.
   */
  async addBoothStaff(boothId: string, staffId: string) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const staffIds = booth.staffIds || [];
    if (staffIds.includes(staffId)) {
      throw new ConflictException('Staff member already assigned to this booth');
    }

    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: {
        staffIds: [...staffIds, staffId],
      },
    });

    this.logger.log(`Added staff ${staffId} to booth ${boothId}`);
    return updatedBooth;
  }

  /**
   * Removes a staff member from a booth.
   */
  async removeBoothStaff(boothId: string, staffId: string) {
    const booth = await this.prisma.expoBooth.findUnique({
      where: { id: boothId },
    });

    if (!booth) {
      throw new NotFoundException('Booth not found');
    }

    const staffIds = booth.staffIds || [];
    if (!staffIds.includes(staffId)) {
      throw new NotFoundException('Staff member not assigned to this booth');
    }

    // Remove staff from staffIds
    const updatedBooth = await this.prisma.expoBooth.update({
      where: { id: boothId },
      data: {
        staffIds: staffIds.filter((id) => id !== staffId),
      },
    });

    // Also remove their presence record
    await this.prisma.boothStaffPresence.deleteMany({
      where: { boothId, staffId },
    });

    this.logger.log(`Removed staff ${staffId} from booth ${boothId}`);
    return updatedBooth;
  }

  /**
   * Gets booth for a sponsor by their user/org ID.
   * Used by sponsors to find their own booth.
   */
  async getBoothForSponsor(sponsorId: string) {
    return this.prisma.expoBooth.findFirst({
      where: { sponsorId },
      include: {
        staffPresence: true,
        expoHall: {
          select: {
            id: true,
            eventId: true,
            name: true,
          },
        },
        _count: {
          select: {
            visits: true,
            chatMessages: true,
          },
        },
      },
    });
  }
}
