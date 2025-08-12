import { Test, TestingModule } from '@nestjs/testing';
import { CirclesGateway } from './circles.gateway';
import { CirclesService } from './circles.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockCirclesService = {
  createCircle: jest.fn(),
  joinCircle: jest.fn(),
  leaveCircle: jest.fn(),
  closeCircle: jest.fn(),
};
const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('CirclesGateway', () => {
  let gateway: CirclesGateway;

  const mockClient = {
    handshake: { query: { sessionId: 'session-123' } },
  } as any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        CirclesGateway,
        { provide: CirclesService, useValue: mockCirclesService },
      ],
    }).compile();
    gateway = module.get<CirclesGateway>(CirclesGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  it('handleCreateCircle should broadcast the "circle.opened" event', async () => {
    mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
    const newCircle = { id: 'circle-1' };
    mockCirclesService.createCircle.mockResolvedValue(newCircle);

    await gateway.handleCreateCircle(
      { topic: 'Test', idempotencyKey: 'k1' },
      mockClient,
    );

    expect(mockCirclesService.createCircle).toHaveBeenCalled();
    expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
    expect(mockIoServer.emit).toHaveBeenCalledWith('circle.opened', newCircle);
  });

  it('handleJoinCircle should broadcast the "circle.roster.updated" event', async () => {
    mockGetAuthenticatedUser.mockReturnValue({ sub: 'user-1' });
    const updatedRoster = { id: 'circle-1', participants: [] };
    mockCirclesService.joinCircle.mockResolvedValue(updatedRoster);

    await gateway.handleJoinCircle(
      { circleId: 'circle-1', idempotencyKey: 'k2' },
      mockClient,
    );

    expect(mockCirclesService.joinCircle).toHaveBeenCalled();
    expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
    expect(mockIoServer.emit).toHaveBeenCalledWith(
      'circle.roster.updated',
      updatedRoster,
    );
  });
});
