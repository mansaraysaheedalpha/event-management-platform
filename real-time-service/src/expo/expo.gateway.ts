// src/expo/expo.gateway.ts
import {
  ConnectedSocket,
  MessageBody,
  OnGatewayDisconnect,
  OnGatewayInit,
  SubscribeMessage,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'socket.io';
import { Logger, OnModuleDestroy } from '@nestjs/common';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getErrorMessage } from 'src/common/utils/error.utils';
import { ExpoService } from './expo.service';
import { ExpoAnalyticsService } from './expo-analytics.service';
import {
  EnterHallDto,
  EnterBoothDto,
  LeaveBoothDto,
  SendBoothChatDto,
  GetBoothChatHistoryDto,
  RequestVideoCallDto,
  AcceptVideoCallDto,
  DeclineVideoCallDto,
  EndVideoCallDto,
  TrackResourceDownloadDto,
  TrackCtaClickDto,
  CaptureLeadDto,
  UpdateStaffPresenceDto,
  JoinBoothAsStaffDto,
} from './dto';

// Uses ALLOWED_ORIGINS env var (consistent with main.ts and cors.config.ts)
const CORS_ALLOWED_ORIGINS = process.env.ALLOWED_ORIGINS
  ? process.env.ALLOWED_ORIGINS.split(',').map((origin) => origin.trim())
  : ['http://localhost:3000', 'http://localhost:3001'];

@WebSocketGateway({
  cors: { origin: CORS_ALLOWED_ORIGINS, credentials: true },
  namespace: '/events',
})
export class ExpoGateway implements OnGatewayDisconnect, OnGatewayInit, OnModuleDestroy {
  private readonly logger = new Logger(ExpoGateway.name);
  @WebSocketServer() server: Server;

  // Rate limiting for chat
  private chatRateLimits: Map<string, number> = new Map();
  private readonly CHAT_RATE_LIMIT_MS = 500;
  private readonly MAX_MESSAGE_LENGTH = 2000;
  private readonly RATE_LIMIT_CLEANUP_INTERVAL_MS = 60000; // 1 minute
  private readonly RATE_LIMIT_TTL_MS = 300000; // 5 minutes
  private rateLimitCleanupInterval: NodeJS.Timeout | null = null;

  // Track user visits for cleanup on disconnect
  private userVisits: Map<string, { boothId: string; visitId: string }> = new Map();
  private staffSockets: Map<string, { boothId: string; staffId: string }> = new Map();

  constructor(
    private readonly expoService: ExpoService,
    private readonly analyticsService: ExpoAnalyticsService,
  ) {}

  /**
   * Initialize rate limit cleanup interval
   */
  afterInit() {
    this.rateLimitCleanupInterval = setInterval(() => {
      this.cleanupStaleRateLimits();
    }, this.RATE_LIMIT_CLEANUP_INTERVAL_MS);
    this.logger.log('Expo gateway initialized with rate limit cleanup');
  }

  /**
   * Clean up resources on module destroy
   */
  onModuleDestroy() {
    if (this.rateLimitCleanupInterval) {
      clearInterval(this.rateLimitCleanupInterval);
      this.rateLimitCleanupInterval = null;
    }
    this.chatRateLimits.clear();
    this.userVisits.clear();
    this.staffSockets.clear();
    this.logger.log('Expo gateway cleanup complete');
  }

  /**
   * Remove stale rate limit entries older than TTL
   */
  private cleanupStaleRateLimits() {
    const now = Date.now();
    let cleanedCount = 0;

    for (const [key, timestamp] of this.chatRateLimits.entries()) {
      if (now - timestamp > this.RATE_LIMIT_TTL_MS) {
        this.chatRateLimits.delete(key);
        cleanedCount++;
      }
    }

    if (cleanedCount > 0) {
      this.logger.debug(`Cleaned up ${cleanedCount} stale rate limit entries`);
    }
  }

  /**
   * Handle client disconnection - cleanup visits and staff presence
   */
  async handleDisconnect(client: AuthenticatedSocket) {
    const socketId = client.id;

    try {
      // Cleanup visitor
      await this.expoService.closeVisitBySocket(socketId);

      // Cleanup staff presence
      await this.expoService.markStaffOffline(socketId);

      // Clean up tracking maps
      this.userVisits.delete(socketId);
      this.staffSockets.delete(socketId);
    } catch (error) {
      this.logger.error(`Disconnect cleanup error: ${getErrorMessage(error)}`);
    }
  }

  // ==========================================
  // EXPO HALL EVENTS
  // ==========================================

  /**
   * Enter the expo hall - returns hall data with all booths
   */
  @SubscribeMessage('expo.enter')
  async handleEnterHall(
    @MessageBody() dto: EnterHallDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const hall = await this.expoService.enterHall(user.sub, dto.eventId);

      // Join expo hall room for updates
      await client.join(`expo:${dto.eventId}`);

      this.logger.log(`User ${user.sub} entered expo hall for event ${dto.eventId}`);
      return { success: true, hall };
    } catch (error) {
      this.logger.error(`Failed to enter expo hall: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Leave the expo hall
   */
  @SubscribeMessage('expo.leave')
  async handleLeaveHall(
    @MessageBody() data: { eventId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      await client.leave(`expo:${data.eventId}`);
      this.logger.log(`User ${user.sub} left expo hall for event ${data.eventId}`);
      return { success: true };
    } catch (error) {
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // EXPO HALL MANAGEMENT (ORGANIZERS)
  // ==========================================

  /**
   * Get expo hall info (doesn't throw if not found)
   */
  @SubscribeMessage('expo.hall.get')
  async handleGetHall(
    @MessageBody() data: { eventId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    try {
      const hall = await this.expoService.getExpoHallSafe(data.eventId);
      return { success: true, hall };
    } catch (error) {
      this.logger.error(`Failed to get expo hall: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Create an expo hall (organizer only)
   */
  @SubscribeMessage('expo.hall.create')
  async handleCreateHall(
    @MessageBody() data: {
      eventId: string;
      name: string;
      description?: string;
      categories?: string[];
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    // Check for organizer permission
    const hasPermission = user.permissions?.includes('expo:manage') ||
                          user.permissions?.includes('event:manage');
    if (!hasPermission) {
      return { success: false, error: 'You do not have permission to create expo halls' };
    }

    try {
      const hall = await this.expoService.createExpoHall(data.eventId, user.orgId, {
        name: data.name,
        description: data.description,
        categories: data.categories,
      });

      this.logger.log(`Expo hall ${hall.id} created by ${user.sub}`);
      return { success: true, hall };
    } catch (error) {
      this.logger.error(`Failed to create expo hall: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Update an expo hall (organizer only)
   */
  @SubscribeMessage('expo.hall.update')
  async handleUpdateHall(
    @MessageBody() data: {
      hallId: string;
      name?: string;
      description?: string;
      categories?: string[];
      isActive?: boolean;
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    // Check for organizer permission
    const hasPermission = user.permissions?.includes('expo:manage') ||
                          user.permissions?.includes('event:manage');
    if (!hasPermission) {
      return { success: false, error: 'You do not have permission to update expo halls' };
    }

    try {
      const hall = await this.expoService.updateExpoHall(data.hallId, {
        name: data.name,
        description: data.description,
        categories: data.categories,
        isActive: data.isActive,
      });

      this.logger.log(`Expo hall ${hall.id} updated by ${user.sub}`);
      return { success: true, hall };
    } catch (error) {
      this.logger.error(`Failed to update expo hall: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Create a booth in an expo hall (organizer only)
   */
  @SubscribeMessage('expo.booth.create')
  async handleCreateBooth(
    @MessageBody() data: {
      hallId: string;
      name: string;
      tagline?: string;
      description?: string;
      tier?: string;
      logoUrl?: string;
      bannerUrl?: string;
      videoUrl?: string;
      category?: string;
    },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    // Check for organizer permission
    const hasPermission = user.permissions?.includes('expo:manage') ||
                          user.permissions?.includes('event:manage');
    if (!hasPermission) {
      return { success: false, error: 'You do not have permission to create booths' };
    }

    try {
      const booth = await this.expoService.createBooth(data.hallId, user.orgId, {
        name: data.name,
        tagline: data.tagline,
        description: data.description,
        tier: data.tier as 'PLATINUM' | 'GOLD' | 'SILVER' | 'BRONZE' | 'STARTUP' | undefined,
        logoUrl: data.logoUrl,
        bannerUrl: data.bannerUrl,
        videoUrl: data.videoUrl,
        category: data.category,
      });

      this.logger.log(`Booth ${booth.id} created by ${user.sub}`);
      return { success: true, booth };
    } catch (error) {
      this.logger.error(`Failed to create booth: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // BOOTH VISIT EVENTS
  // ==========================================

  /**
   * Enter a booth
   */
  @SubscribeMessage('expo.booth.enter')
  async handleEnterBooth(
    @MessageBody() dto: EnterBoothDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const visit = await this.expoService.enterBooth(
        user.sub,
        dto.boothId,
        dto.eventId,
        client.id,
      );

      // Join booth room for chat and updates
      await client.join(`booth:${dto.boothId}`);

      // Track for disconnect cleanup
      this.userVisits.set(client.id, { boothId: dto.boothId, visitId: visit.id });

      // Update analytics
      await this.analyticsService.updateVisitorMetrics(dto.boothId);

      // Get current visitor count
      const visitorCount = await this.expoService.getBoothVisitorCount(dto.boothId);

      // Broadcast visitor update to booth and expo hall
      this.server.to(`booth:${dto.boothId}`).emit('expo.booth.visitors.update', {
        boothId: dto.boothId,
        visitorCount,
      });

      this.server.to(`expo:${dto.eventId}`).emit('expo.booth.visitors.update', {
        boothId: dto.boothId,
        visitorCount,
      });

      // Notify booth staff of new visitor
      this.server.to(`booth-staff:${dto.boothId}`).emit('expo.booth.visitor.entered', {
        visitorId: user.sub,
        visitorName: user.firstName && user.lastName
          ? `${user.firstName} ${user.lastName}`
          : user.email,
        visitId: visit.id,
      });

      const booth = await this.expoService.getBooth(dto.boothId);

      return { success: true, booth, visitId: visit.id };
    } catch (error) {
      this.logger.error(`Failed to enter booth: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Leave a booth
   */
  @SubscribeMessage('expo.booth.leave')
  async handleLeaveBooth(
    @MessageBody() dto: LeaveBoothDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const visit = await this.expoService.leaveBooth(user.sub, dto.boothId);

      if (visit) {
        // Update analytics
        await this.analyticsService.updateVisitorMetrics(dto.boothId);
        await this.analyticsService.updateAvgVisitDuration(dto.boothId, visit.durationSeconds);
      }

      // Leave booth room
      await client.leave(`booth:${dto.boothId}`);
      this.userVisits.delete(client.id);

      // Get current visitor count
      const visitorCount = await this.expoService.getBoothVisitorCount(dto.boothId);

      // Broadcast visitor update
      this.server.to(`booth:${dto.boothId}`).emit('expo.booth.visitors.update', {
        boothId: dto.boothId,
        visitorCount,
      });

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to leave booth: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // BOOTH CHAT EVENTS
  // ==========================================

  /**
   * Join booth chat
   */
  @SubscribeMessage('expo.booth.chat.join')
  async handleJoinChat(
    @MessageBody() data: { boothId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Already joined in enterBooth, but this allows explicit join
      await client.join(`booth:${data.boothId}`);

      return { success: true };
    } catch (error) {
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Send chat message
   */
  @SubscribeMessage('expo.booth.chat.send')
  async handleSendChat(
    @MessageBody() dto: SendBoothChatDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    // Validate message
    if (!dto.text?.trim()) {
      return { success: false, error: 'Message cannot be empty' };
    }

    if (dto.text.length > this.MAX_MESSAGE_LENGTH) {
      return { success: false, error: `Message too long (max ${this.MAX_MESSAGE_LENGTH} characters)` };
    }

    // Rate limiting
    const rateLimitKey = `${user.sub}:${dto.boothId}`;
    const lastMessageTime = this.chatRateLimits.get(rateLimitKey) || 0;
    const now = Date.now();
    if (now - lastMessageTime < this.CHAT_RATE_LIMIT_MS) {
      return { success: false, error: 'Please wait before sending another message' };
    }

    try {
      const isStaff = await this.expoService.isBoothStaff(user.sub, dto.boothId);

      const userName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Anonymous';

      const message = await this.expoService.sendBoothChat(
        user.sub,
        userName,
        null, // avatarUrl not available in JWT
        dto.boothId,
        dto.text.trim(),
        isStaff,
      );

      // Update rate limit
      this.chatRateLimits.set(rateLimitKey, now);

      // Track chat message
      await this.analyticsService.trackChatMessage(dto.boothId);

      // Broadcast to booth room
      this.server.to(`booth:${dto.boothId}`).emit('expo.booth.chat.message', message);

      return { success: true, message };
    } catch (error) {
      this.logger.error(`Failed to send chat: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Get chat history
   */
  @SubscribeMessage('expo.booth.chat.history')
  async handleGetChatHistory(
    @MessageBody() dto: GetBoothChatHistoryDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    try {
      const result = await this.expoService.getBoothChatHistory(
        dto.boothId,
        dto.limit || 50,
        dto.cursor,
      );

      return { success: true, ...result };
    } catch (error) {
      this.logger.error(`Failed to get chat history: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // VIDEO CALL EVENTS
  // ==========================================

  /**
   * Request video call with staff
   */
  @SubscribeMessage('expo.booth.video.request')
  async handleVideoRequest(
    @MessageBody() dto: RequestVideoCallDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const userName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Anonymous';

      const session = await this.expoService.requestVideoCall(
        user.sub,
        userName,
        dto.boothId,
        dto.message,
      );

      // Notify staff of video request
      this.server.to(`booth-staff:${dto.boothId}`).emit('expo.booth.video.requested', {
        sessionId: session.id,
        attendeeId: user.sub,
        attendeeName: userName,
        message: dto.message,
        requestedAt: session.requestedAt,
      });

      return { success: true, session };
    } catch (error) {
      this.logger.error(`Failed to request video call: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Staff accepts video call
   */
  @SubscribeMessage('expo.booth.video.accept')
  async handleVideoAccept(
    @MessageBody() dto: AcceptVideoCallDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const staffName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Staff';

      const session = await this.expoService.acceptVideoCall(
        user.sub,
        staffName,
        dto.sessionId,
      );

      // Notify attendee that call was accepted
      this.server.to(`booth:${session.boothId}`).emit('expo.booth.video.accepted', {
        sessionId: session.id,
        staffId: session.staffId,
        staffName: session.staffName,
        videoRoomUrl: session.videoRoomUrl,
        attendeeToken: session.attendeeToken,
      });

      return {
        success: true,
        session: {
          ...session,
          token: session.staffToken, // Return staff token to the accepting staff
        },
      };
    } catch (error) {
      this.logger.error(`Failed to accept video call: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Staff declines video call
   */
  @SubscribeMessage('expo.booth.video.decline')
  async handleVideoDecline(
    @MessageBody() dto: DeclineVideoCallDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const session = await this.expoService.declineVideoCall(
        user.sub,
        dto.sessionId,
        dto.reason,
      );

      // Notify attendee that call was declined
      this.server.to(`booth:${session.boothId}`).emit('expo.booth.video.declined', {
        sessionId: session.id,
        reason: dto.reason,
      });

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to decline video call: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * End video call
   */
  @SubscribeMessage('expo.booth.video.end')
  async handleVideoEnd(
    @MessageBody() dto: EndVideoCallDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const session = await this.expoService.endVideoCall(dto.sessionId, user.sub);

      // Track video session completion
      await this.analyticsService.trackVideoSession(
        session.boothId,
        session.durationSeconds,
        true,
      );

      // Notify both parties
      this.server.to(`booth:${session.boothId}`).emit('expo.booth.video.ended', {
        sessionId: session.id,
        endedBy: user.sub,
        durationSeconds: session.durationSeconds,
      });

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to end video call: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // ENGAGEMENT TRACKING EVENTS
  // ==========================================

  /**
   * Track resource download
   */
  @SubscribeMessage('expo.booth.resource.download')
  async handleResourceDownload(
    @MessageBody() dto: TrackResourceDownloadDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const visitInfo = this.userVisits.get(client.id);

      await this.analyticsService.trackResourceDownload(
        user.sub,
        dto.boothId,
        dto.resourceId,
        visitInfo?.visitId,
      );

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to track download: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Track CTA click
   */
  @SubscribeMessage('expo.booth.cta.click')
  async handleCtaClick(
    @MessageBody() dto: TrackCtaClickDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const visitInfo = this.userVisits.get(client.id);

      await this.analyticsService.trackCtaClick(
        user.sub,
        dto.boothId,
        dto.ctaId,
        visitInfo?.visitId,
      );

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to track CTA click: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Capture lead information
   */
  @SubscribeMessage('expo.booth.lead.capture')
  async handleLeadCapture(
    @MessageBody() dto: CaptureLeadDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const visitInfo = this.userVisits.get(client.id);

      if (!visitInfo) {
        return { success: false, error: 'You must be visiting the booth to submit lead info' };
      }

      await this.analyticsService.trackLeadCapture(
        user.sub,
        dto.boothId,
        visitInfo.visitId,
        dto.formData || {},
      );

      // Notify staff of new lead
      this.server.to(`booth-staff:${dto.boothId}`).emit('expo.booth.lead.captured', {
        visitorId: user.sub,
        visitorName: user.firstName && user.lastName
          ? `${user.firstName} ${user.lastName}`
          : user.email,
        formData: dto.formData,
      });

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to capture lead: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // STAFF PRESENCE EVENTS
  // ==========================================

  /**
   * Staff joins booth management
   */
  @SubscribeMessage('expo.booth.staff.join')
  async handleStaffJoin(
    @MessageBody() dto: JoinBoothAsStaffDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const staffName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Staff';

      await this.expoService.updateStaffPresence(
        user.sub,
        staffName,
        null, // avatarUrl not available in JWT
        dto.boothId,
        'ONLINE',
        client.id,
      );

      // Join staff-specific room
      await client.join(`booth-staff:${dto.boothId}`);
      await client.join(`booth:${dto.boothId}`);

      // Track for disconnect cleanup
      this.staffSockets.set(client.id, { boothId: dto.boothId, staffId: user.sub });

      // Get pending video requests
      const pendingRequests = await this.expoService.getPendingVideoRequests(dto.boothId);

      // Broadcast staff availability update
      const staffPresence = await this.expoService.getBoothStaffPresence(dto.boothId);
      this.server.to(`booth:${dto.boothId}`).emit('expo.booth.staff.available', {
        boothId: dto.boothId,
        staff: staffPresence,
      });

      return { success: true, pendingRequests };
    } catch (error) {
      this.logger.error(`Failed to join as staff: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  /**
   * Update staff presence status
   */
  @SubscribeMessage('expo.booth.staff.status')
  async handleStaffStatusUpdate(
    @MessageBody() dto: UpdateStaffPresenceDto,
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      const staffName = user.firstName && user.lastName
        ? `${user.firstName} ${user.lastName}`
        : user.email || 'Staff';

      await this.expoService.updateStaffPresence(
        user.sub,
        staffName,
        null, // avatarUrl not available in JWT
        dto.boothId,
        dto.status as never,
        client.id,
      );

      // Broadcast staff availability update
      const staffPresence = await this.expoService.getBoothStaffPresence(dto.boothId);
      this.server.to(`booth:${dto.boothId}`).emit('expo.booth.staff.available', {
        boothId: dto.boothId,
        staff: staffPresence,
      });

      return { success: true };
    } catch (error) {
      this.logger.error(`Failed to update staff status: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }

  // ==========================================
  // ANALYTICS EVENTS
  // ==========================================

  /**
   * Get real-time booth analytics (for sponsor dashboard)
   */
  @SubscribeMessage('expo.booth.analytics')
  async handleGetAnalytics(
    @MessageBody() data: { boothId: string },
    @ConnectedSocket() client: AuthenticatedSocket,
  ) {
    const user = getAuthenticatedUser(client);

    try {
      // Verify user is staff for this booth
      const isStaff = await this.expoService.isBoothStaff(user.sub, data.boothId);
      if (!isStaff) {
        return { success: false, error: 'You are not authorized to view booth analytics' };
      }

      const stats = await this.analyticsService.getRealtimeStats(data.boothId);

      return { success: true, stats };
    } catch (error) {
      this.logger.error(`Failed to get analytics: ${getErrorMessage(error)}`);
      return { success: false, error: getErrorMessage(error) };
    }
  }
}
