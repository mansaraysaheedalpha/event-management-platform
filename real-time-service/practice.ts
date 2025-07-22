import { Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { JwtService } from '@nestjs/jwt';
import {
  OnGatewayConnection,
  OnGatewayDisconnect,
  WebSocketGateway,
  WebSocketServer,
} from '@nestjs/websockets';
import { Server } from 'http';
import { Socket } from 'socket.io';

interface JwtPayload {
  sub: string;
  email: string;
  role?: string;
}

interface AuthenticatedSocket extends Socket {
  data: {
    user: JwtPayload;
  };
}

const extractTokenSafely = (client: Socket) => {
  const authHeader = client.handshake.auth;
  if (authHeader && typeof authHeader.token === 'string') {
    return authHeader.token.replace('Bearer', '').trim();
  }

  const queryToken = client.handshake.query?.token;
  if (typeof queryToken === 'string') {
    return queryToken;
  }

  if (Array.isArray(queryToken) && queryToken.length > 0) {
    return queryToken[0];
  }

  return null;
};

@WebSocketGateway({
  cors: {
    origin: '*',
    credential: true,
  },
  namepsapce: '/events',
})
export class EventsGateway implements OnGatewayConnection, OnGatewayDisconnect {
  private readonly logger = new Logger(EventsGateway.name);

  @WebSocketServer()
  server: Server;

  constructor(
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
  ) {}

  async handleConnection(client: AuthenticatedSocket) {
    try {
      // retrieve the token from the client
      const token = extractTokenSafely(client);
      // if not token send a warning and disconnect
      if (!token) {
        this.logger.warn(`Missing token, disconnection user ${client.id}`);
        client.disconnect(true);
        return;
      }

      // if token verify it and return the payload
      const payload = this.jwtService.verify<JwtPayload>(token, {
        secret: this.configService.get<string>('JWT_SECRET'),
      });
      // atach the payload to the client
      client.data.user = payload;
      // emit a success message
      this.logger.log('');
      this.server.emit('connected', {
        message: '',
        userId: payload.sub,
      });
    } catch (error) {
      this.logger.error('');
      this.server.emit('error', {
        message: 'Authentication error occurred',
        code: 'UNAUTHORIZED',
      });
    }
  }

  async handleDisconnect(client: any) {
    
  }
}
