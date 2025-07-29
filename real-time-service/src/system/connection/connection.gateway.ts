import { WebSocketGateway } from '@nestjs/websockets';
import { Logger } from '@nestjs/common';
import { ConnectionService } from './connection.service';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';

@WebSocketGateway({
  cors: { origin: '*', credentials: true },
  namespace: '/events',
})
export class ConnectionGateway {
  private readonly logger = new Logger(ConnectionGateway.name);

  constructor(
    private readonly connectionService: ConnectionService,
    private readonly jwtService: JwtService,
    private readonly configService: ConfigService,
  ) {}
}
