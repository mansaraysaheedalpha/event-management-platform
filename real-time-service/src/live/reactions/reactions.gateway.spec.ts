import { Test, TestingModule } from '@nestjs/testing';
import { ReactionsGateway } from './reactions.gateway';
import { ReactionsService } from './reactions.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

describe('ReactionsGateway', () => {
  let module: TestingModule;
  let gateway: ReactionsGateway;
  let redis: any;

  const mockIoServer = {
    to: jest.fn().mockReturnThis(),
    emit: jest.fn(),
  };

  // Set up fake timers once for the entire test suite
  beforeAll(() => {
    jest.useFakeTimers();
  });

  // Restore real timers when all tests are done
  afterAll(() => {
    jest.useRealTimers();
  });

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        ReactionsGateway,
        { provide: ReactionsService, useValue: { addReaction: jest.fn() } },
        {
          provide: REDIS_CLIENT,
          useValue: {
            multi: jest.fn().mockReturnThis(),
            hgetall: jest.fn().mockReturnThis(),
            del: jest.fn().mockReturnThis(),
            exec: jest.fn(),
          },
        },
      ],
    }).compile();

    gateway = module.get<ReactionsGateway>(ReactionsGateway);
    redis = module.get(REDIS_CLIENT);
    (gateway as any).server = mockIoServer;

    // Reset all mocks before each test
    jest.clearAllMocks();
    mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
  });

  // Clean up after each test to prevent leaks
  afterEach(async () => {
    // **THE KEY FIX**: This empties the timer queue after each test
    jest.clearAllTimers();
    await module.close();
  });

  it('should add a reaction and start the broadcast loop', async () => {
    const setTimeoutSpy = jest.spyOn(global, 'setTimeout');
    const mockClient = {
      handshake: { query: { sessionId: 'session-1' } },
    } as any;

    await gateway.handleSendReaction({ emoji: '🔥' }, mockClient);

    const reactionsService = module.get<ReactionsService>(ReactionsService);
    expect(reactionsService.addReaction).toHaveBeenCalledWith(
      'session-1',
      'user-1',
      '🔥',
    );
    expect(setTimeoutSpy).toHaveBeenCalledTimes(1);

    setTimeoutSpy.mockRestore();
  });

  it('should broadcast reactions and continue the loop', async () => {
    const setTimeoutSpy = jest.spyOn(global, 'setTimeout');
    const reactionCounts = { '🔥': '5', '❤️': '10' };
    redis.exec.mockResolvedValue([
      [null, reactionCounts],
      [null, 1],
    ]);

    (gateway as any).scheduleNextBroadcast('session-1');
    await jest.advanceTimersByTimeAsync(2000);

    const expectedPayload = { '🔥': 5, '❤️': 10 };
    expect(mockIoServer.to).toHaveBeenCalledWith('session:session-1');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'reaction.burst',
      expectedPayload,
    );

    // The loop schedules itself once to start, and once to continue.
    expect(setTimeoutSpy).toHaveBeenCalledTimes(2);

    setTimeoutSpy.mockRestore();
  });

  it('should stop the loop if no reactions are found', async () => {
    const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');
    redis.exec.mockResolvedValue([
      [null, {}],
      [null, 1],
    ]);

    (gateway as any).scheduleNextBroadcast('session-1');
    await jest.advanceTimersByTimeAsync(2000);

    expect(mockIoServer.emit).not.toHaveBeenCalled();
    expect(clearTimeoutSpy).toHaveBeenCalled();

    clearTimeoutSpy.mockRestore();
  });
});
