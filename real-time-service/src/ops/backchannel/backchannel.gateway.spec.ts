import { Test, TestingModule } from '@nestjs/testing';
import { BackchannelGateway } from './backchannel.gateway';
import { BackchannelService } from './backchannel.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { TargetableRole } from './dto/send-backchannel-message.dto'; // **FIX**: Import the enum

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockService = { sendMessage: jest.fn() };
const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('BackchannelGateway', () => {
  let gateway: BackchannelGateway;

  const mockClient = {
    id: 'socket-1',
    join: jest.fn(),
    handshake: { query: { sessionId: 'session-123' } },
  } as any;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        BackchannelGateway,
        { provide: BackchannelService, useValue: mockService },
      ],
    }).compile();
    gateway = module.get<BackchannelGateway>(BackchannelGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  it('should broadcast to the main backchannel room for a general message', async () => {
    mockGetAuthenticatedUser.mockReturnValue({
      sub: 'admin-1',
      permissions: ['backchannel:send'],
    });
    const messageDto = { text: 'Hello all', idempotencyKey: 'k1' };
    mockService.sendMessage.mockResolvedValue({ id: 'msg-1', ...messageDto });

    await gateway.handleSendMessage(messageDto, mockClient);

    expect(mockIoServer.to).toHaveBeenCalledWith('backchannel:session-123');
  });

  it('should broadcast to specific rooms for a role-targeted whisper', async () => {
    mockGetAuthenticatedUser.mockReturnValue({
      sub: 'admin-1',
      permissions: ['backchannel:send'],
    });
    // **FIX**: Use the enum instead of a string
    const messageDto = {
      text: 'For speakers only',
      idempotencyKey: 'k2',
      targetRole: TargetableRole.SPEAKER,
    };
    mockService.sendMessage.mockResolvedValue({ id: 'msg-2', ...messageDto });

    await gateway.handleSendMessage(messageDto, mockClient);

    expect(mockIoServer.to).toHaveBeenCalledWith(
      'backchannel:session-123:role:SPEAKER',
    );
    expect(mockIoServer.to).toHaveBeenCalledWith('socket-1');
  });
});
