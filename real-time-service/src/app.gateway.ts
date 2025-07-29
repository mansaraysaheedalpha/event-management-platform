import {
  OnGatewayConnection,
  OnGatewayDisconnect,
  WebSocketGateway,
} from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import { AuthenticatedSocket } from './common/interfaces/auth.interface';
import { ConnectionService } from './system/connection/connection.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';
import { JwtPayload } from './common/interfaces/auth.interface';
import { getErrorMessage } from './common/utils/error.utils';
import { Server } from 'socket.io';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class AppGateway implements OnGatewayConnection, OnGatewayDisconnect {
  private readonly logger = new Logger('AppGateway');

  constructor(
    private readonly connectionService: ConnectionService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
  ) {}

  afterInit(server: Server) {
    server.setMaxListeners(20); // or a higher value if needed
  }

  /**
   * Handles all new client connections for the entire application.
   */
  async handleConnection(client: AuthenticatedSocket) {
    try {
      const token = client.handshake.headers.authorization?.split(' ')[1];
      if (!token) {
        throw new Error('Missing authentication token.');
      }

      const payload = this.jwtService.verify<JwtPayload>(token, {
        secret: this.configService.get<string>('JWT_SECRET'),
      });
      client.data.user = payload;

      await client.join(`user:${payload.sub}`);

      this.logger.log(
        `✅ Client Connected: ${client.id} | User: ${payload.email}`,
      );

      client.emit('connectionAcknowledged', { userId: payload.sub });
      this.connectionService.startHeartbeat(client);
    } catch (error) {
      this.logger.error(
        `🔴 Auth error for client ${client.id}: ${getErrorMessage(error)}`,
      );
      client.emit('systemError', { message: 'Authentication failed.' });
      client.disconnect(true);
    }
  }

  /**
   * Handles all client disconnections for the entire application.
   */
  handleDisconnect(client: AuthenticatedSocket) {
    this.logger.log(`❌ Client Disconnected: ${client.id}`);
    this.connectionService.stopHeartbeat(client.id);
  }
}
