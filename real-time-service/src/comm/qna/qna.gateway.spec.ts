import { Test, TestingModule } from '@nestjs/testing';
import { QnaGateway } from './qna.gateway';
import { QnaService } from './qna.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Handshake } from 'socket.io/dist/socket-types';
import { ModerateQuestionDto } from './dto/moderate-question.dto';
import { ForbiddenException } from '@nestjs/common';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockQnaService = {
  askQuestion: jest.fn(),
  upvoteQuestion: jest.fn(),
  moderateQuestion: jest.fn(),
  answerQuestion: jest.fn(),
  tagQuestion: jest.fn(),
};

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('QnaGateway', () => {
  let gateway: QnaGateway;

  const mockHandshake: Handshake = {
    headers: {},
    time: new Date().toUTCString(),
    address: '127.0.0.1',
    xdomain: false,
    secure: false,
    issued: Date.now(),
    url: '/socket.io/',
    query: { sessionId: 'session-123' },
    auth: {},
  };
  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: mockHandshake,
  };
  const mockUser = { sub: 'user-1', email: 'test@test.com' };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        QnaGateway,
        { provide: QnaService, useValue: mockQnaService },
      ],
    }).compile();

    gateway = module.get<QnaGateway>(QnaGateway);
    (gateway as any).server = mockIoServer;

    jest.clearAllMocks();
    mockGetAuthenticatedUser.mockReturnValue(mockUser);
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });

  describe('handleAskQuestion', () => {
    it('should call the service and broadcast to public and moderation rooms', async () => {
      const askDto = { text: 'Q?', idempotencyKey: 'k1' };
      const newQuestion = { id: 'q-1' };
      mockQnaService.askQuestion.mockResolvedValue(newQuestion);

      await gateway.handleAskQuestion(
        askDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockQnaService.askQuestion).toHaveBeenCalledWith(
        mockUser.sub,
        mockUser.email,
        'session-123',
        askDto,
      );
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.to).toHaveBeenCalledWith(
        'session:session-123:moderation',
      );
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'qa.question.new',
        newQuestion,
      );
      expect(mockIoServer.emit).toHaveBeenCalledTimes(2);
    });
  });

  describe('handleModerateQuestion', () => {
    const moderateDto: ModerateQuestionDto = {
      questionId: 'q-1',
      status: 'approved',
      idempotencyKey: 'k2',
    };

    it('should broadcast to both rooms on approval', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        ...mockUser,
        permissions: ['qna:moderate'],
      });
      const updatedQuestion = { id: 'q-1', status: 'approved' };
      mockQnaService.moderateQuestion.mockResolvedValue(updatedQuestion);

      await gateway.handleModerateQuestion(
        moderateDto,
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.to).toHaveBeenCalledWith(
        'session:session-123:moderation',
      );
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'qna.question.updated',
        updatedQuestion,
      );
      expect(mockIoServer.emit).toHaveBeenCalledTimes(2);
    });

    it('should broadcast removal on dismissal', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        ...mockUser,
        permissions: ['qna:moderate'],
      });
      const updatedQuestion = { id: 'q-1', status: 'dismissed' };
      mockQnaService.moderateQuestion.mockResolvedValue(updatedQuestion);

      await gateway.handleModerateQuestion(
        { ...moderateDto, status: 'dismissed' },
        mockClientSocket as AuthenticatedSocket,
      );

      // Moderation room gets the full update
      expect(mockIoServer.to).toHaveBeenCalledWith(
        'session:session-123:moderation',
      );
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'qna.question.updated',
        updatedQuestion,
      );
      // Public room gets the removal event
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.emit).toHaveBeenCalledWith('qna.question.removed', {
        questionId: 'q-1',
      });
    });

    // **FIXED TEST CASE**
    it('should throw ForbiddenException if user lacks permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        ...mockUser,
        permissions: [],
      }); // No permission

      // Expect the gateway method to reject with a ForbiddenException
      await expect(
        gateway.handleModerateQuestion(
          moderateDto,
          mockClientSocket as AuthenticatedSocket,
        ),
      ).rejects.toThrow(ForbiddenException);

      expect(mockQnaService.moderateQuestion).not.toHaveBeenCalled();
    });
  });

  describe('broadcastModerationAlert', () => {
    it('should emit an alert to the correct moderation room', () => {
      const payload = { type: 'HIGH_VOLUME' };
      gateway.broadcastModerationAlert('session-abc', payload);

      expect(mockIoServer.to).toHaveBeenCalledWith(
        'session:session-abc:moderation',
      );
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'moderation.alert',
        payload,
      );
    });
  });
});
