import { Injectable, Logger, Inject, forwardRef } from '@nestjs/common';
import { OnEvent } from '@nestjs/event-emitter';
import { PrismaService } from 'src/prisma.service';
import { SyncGateway } from './sync.gateway';

interface SyncEventPayload {
  resource: 'MESSAGE' | 'POLL' | 'QUESTION';
  action: 'CREATED' | 'UPDATED' | 'DELETED';
  payload: { sessionId: string; [key: string]: any };
}

@Injectable()
export class SyncService {
  private readonly logger = new Logger(SyncService.name);

  constructor(
    private readonly prisma: PrismaService,
    @Inject(forwardRef(() => SyncGateway))
    private readonly syncGateway: SyncGateway,
  ) {}

  @OnEvent('sync-events')
  async handleSyncEvent(event: SyncEventPayload) {
    this.logger.log(`Processing sync event for resource: ${event.resource}`);

    // Find all participants of the session where the change occurred
    // In a production system, this list of participants would be heavily cached in Redis.
    const session = await this.prisma.chatSession.findUnique({
      where: { id: event.payload.sessionId },
      select: { participants: true },
    });

    if (!session) return;

    // Send a targeted sync update to each participant
    for (const userId of session.participants) {
      this.syncGateway.sendSyncUpdate(userId, event);
    }
  }

  /**
   * Fetches all changes for a user since a given timestamp.
   */
  async getChangesSince(userId: string, since: string) {
    const sinceDate = new Date(since);

    const changes = await this.prisma.syncLog.findMany({
      where: {
        userId: userId,
        timestamp: {
          gt: sinceDate, // Get records greater than the 'since' date
        },
      },
      orderBy: {
        timestamp: 'asc',
      },
    });

    return changes;
  }
}
