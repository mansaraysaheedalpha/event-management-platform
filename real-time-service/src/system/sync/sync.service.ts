import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { PrismaService } from 'src/prisma.service';
import { SyncGateway } from './sync.gateway';

interface SyncEventPayload {
  resource: 'MESSAGE' | 'POLL' | 'QUESTION';
  action: 'CREATED' | 'UPDATED' | 'DELETED';
  payload: { sessionId: string; [key: string]: any };
}

/**
 * The `SyncService` listens to system-wide events and sends
 * real-time updates to users involved in those events.
 * It also provides an endpoint for clients to fetch updates
 * since a specific time.
 *
 * @example
 * // When a new message is created:
 * eventEmitter.emit('sync-events', {
 *   resource: 'MESSAGE',
 *   action: 'CREATED',
 *   payload: { sessionId: 'abc123', content: 'Hello' },
 * });
 */
@Injectable()
export class SyncService {
  private readonly logger = new Logger(SyncService.name);

  constructor(
    private readonly prisma: PrismaService,
    @Inject(forwardRef(() => SyncGateway))
    private readonly syncGateway: SyncGateway,
  ) {}

  /**
   * Handles sync-related events (message, poll, question)
   * and dispatches updates to all participants of the session.
   *
   * @param event - Sync event payload containing resource, action, and session info
   * @returns Promise<void>
   */
  @OnEvent('sync-events')
  async handleSyncEvent(event: SyncEventPayload): Promise<void> {
    this.logger.log(`Processing sync event for resource: ${event.resource}`);

    const session = await this.prisma.chatSession.findUnique({
      where: { id: event.payload.sessionId },
      select: { participants: true },
    });

    if (!session) return;

    for (const userId of session.participants) {
      this.syncGateway.sendSyncUpdate(userId, event);
    }
  }

  /**
   * Fetches all sync changes for a user since a given timestamp.
   * Useful for clients doing a delta-sync after being offline.
   *
   * @param userId - The ID of the user requesting changes
   * @param since - ISO string timestamp to filter changes after
   * @returns Promise<any[]> - Array of sync log entries
   */
  async getChangesSince(userId: string, since: string): Promise<any[]> {
    const sinceDate = new Date(since);

    const changes = await this.prisma.syncLog.findMany({
      where: {
        userId: userId,
        timestamp: {
          gt: sinceDate,
        },
      },
      orderBy: {
        timestamp: 'asc',
      },
    });

    return changes;
  }
}
