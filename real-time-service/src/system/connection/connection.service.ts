//src/system/connection/connection.service.ts
import { Injectable, Logger } from '@nestjs/common';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';

// Define the standard, type-safe reasons for a reconnect
export enum ReconnectReason {
  SERVER_MAINTENANCE = 'SERVER_MAINTENANCE',
  NEW_VERSION_DEPLOYED = 'NEW_VERSION_DEPLOYED',
  SESSION_TERMINATED = 'SESSION_TERMINATED', // e.g., logged in from another device
}

@Injectable()
export class ConnectionService {
  private readonly logger = new Logger(ConnectionService.name);
  private readonly heartbeatTimers = new Map<string, NodeJS.Timeout>();
  private readonly HEARTBEAT_INTERVAL = 30000; // 30 seconds

  /**
   * Starts sending periodic heartbeat events to a client.
   */
  startHeartbeat(client: AuthenticatedSocket): void {
    this.logger.log(`Starting heartbeat for client: ${client.id}`);
    const timer = setInterval(() => {
      client.emit('heartbeat', { timestamp: new Date().toISOString() });
    }, this.HEARTBEAT_INTERVAL);

    this.heartbeatTimers.set(client.id, timer);
  }

  /**
   * Stops the heartbeat for a client upon disconnection.
   */
  stopHeartbeat(clientId: string): void {
    if (this.heartbeatTimers.has(clientId)) {
      this.logger.log(`Stopping heartbeat for client: ${clientId}`);
      clearInterval(this.heartbeatTimers.get(clientId));
      this.heartbeatTimers.delete(clientId);
    }
  }

  /**
   * Sends a reconnect request to a client and disconnects them.
   */
  requestReconnect(
    client: AuthenticatedSocket,
    reason: ReconnectReason,
    retryAfter = 10, // Default to 10 seconds
  ): void {
    const payload = {
      reason,
      retryAfter,
    };
    client.emit('reconnectRequired', payload);
    client.disconnect(true);
  }
}
