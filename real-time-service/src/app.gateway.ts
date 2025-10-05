//src/app.gateway.ts
import {
  OnGatewayConnection,
  OnGatewayDisconnect,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import {
  AuthenticatedSocket,
  JwtPayload,
} from './common/interfaces/auth.interface';
import { ConnectionService } from './system/connection/connection.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { getErrorMessage } from './common/utils/error.utils';
import { extractTokenSafely } from './common/utils/auth.utils';
import { Server } from 'socket.io';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class AppGateway implements OnGatewayConnection, OnGatewayDisconnect {
  @WebSocketServer()
  server: Server;

  private readonly logger = new Logger('AppGateway');

  constructor(
    private readonly connectionService: ConnectionService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
  ) {}

  afterInit(server: Server) {
    server.setMaxListeners(20);
  }

  private handleError(client: AuthenticatedSocket, error: unknown) {
    const errorMessage = getErrorMessage(error);
    this.logger.error(`🔴 Auth error for client ${client.id}: ${errorMessage}`);
    client.emit('systemError', {
      message: 'Authentication failed.',
      reason: errorMessage,
    });
    client.disconnect(true);
  }

  async handleConnection(client: AuthenticatedSocket) {
    try {
      const token = extractTokenSafely(client);

      if (!token) {
        return this.handleError(
          client,
          new Error('Missing authentication token.'),
        );
      }

      const payload = this.jwtService.verify<JwtPayload>(token, {
        secret: this.configService.getOrThrow<string>('JWT_SECRET'),
      });
      client.data.user = payload;

      await client.join(`user:${payload.sub}`);
      this.logger.log(
        `✅ Client Connected: ${client.id} | User: ${payload.email}`,
      );
      client.emit('connectionAcknowledged', { userId: payload.sub });
      this.connectionService.startHeartbeat(client);
    } catch (error) {
      this.handleError(client, error);
    }
  }

  handleDisconnect(client: AuthenticatedSocket) {
    this.logger.log(`❌ Client Disconnected: ${client.id}`);
    this.connectionService.stopHeartbeat(client.id);
  }
}
