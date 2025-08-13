import { Test, TestingModule } from '@nestjs/testing';
import { INestApplication } from '@nestjs/common';
import { AppModule } from '../src/app.module';
import { io, Socket } from 'socket.io-client';
import { JwtService } from '@nestjs/jwt';
import { ConfigService } from '@nestjs/config';

describe('AppGateway (E2E)', () => {
  let app: INestApplication;
  let jwtService: JwtService;
  let configService: ConfigService;
  let port: number;
  let validToken: string;
  let invalidToken: string;
  let socket: Socket; // Keep a reference to the socket for cleanup

  jest.setTimeout(30000);

  beforeAll(async () => {
    const moduleFixture: TestingModule = await Test.createTestingModule({
      imports: [AppModule],
    }).compile();

    app = moduleFixture.createNestApplication();
    jwtService = app.get<JwtService>(JwtService);
    configService = app.get<ConfigService>(ConfigService);

    await app.listen(0);
    port = app.getHttpServer().address().port;

    const jwtSecret = configService.getOrThrow<string>('JWT_SECRET');

    // **FIX**: Create a complete JWT payload, matching the JwtPayload interface
    validToken = jwtService.sign(
      { sub: 'user-123', email: 'test@example.com', orgId: 'org-abc' },
      { secret: jwtSecret },
    );

    invalidToken = 'this.is.an.invalid.token';
  });

  afterAll(async () => {
    await app.close();
  });

  // Good practice: ensure the socket is disconnected after each test
  afterEach(() => {
    if (socket && socket.connected) {
      socket.disconnect();
    }
  });

  it('should allow a client with a valid token to connect', (done) => {
    socket = io(`http://localhost:${port}/events`, {
      transports: ['websocket'],
      auth: { token: validToken },
      path: '/socket.io/',
      // **FIX**: Disable automatic reconnection for predictable tests
      reconnection: false,
    });

    socket.on('connectionAcknowledged', (data) => {
      expect(data.userId).toBe('user-123');
      done(); // Success!
    });

    socket.on('connect_error', (err) => {
      done(err); // Fail the test if a connection error occurs
    });
  });

  it('should reject and disconnect a client with an invalid token', (done) => {
    socket = io(`http://localhost:${port}/events`, {
      transports: ['websocket'],
      auth: { token: invalidToken },
      path: '/socket.io/',
      reconnection: false, // **FIX**: Disable reconnection
    });

    socket.on('systemError', (error) => {
      expect(error.message).toBe('Authentication failed.');
      // Don't call done() here; wait for the disconnect event.
    });

    socket.on('disconnect', (reason) => {
      expect(reason).toBe('io server disconnect');
      done(); // Success!
    });

    // We can also listen for connect_error to make it fail faster
    socket.on('connect_error', (error) => {
      // This is expected, but the 'disconnect' event is the true final state.
      // We don't call done() here.
    });
  });
});
