import { Test, TestingModule } from '@nestjs/testing';
import { ContentGateway } from './content.gateway';
import { ContentService } from './content.service';
import { PrismaService } from 'src/prisma.service';
import { AuthenticatedSocket } from 'src/common/interfaces/auth.interface';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { Handshake } from 'socket.io/dist/socket-types';
import { ForbiddenException } from '@nestjs/common';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockContentService = {
  controlPresentation: jest.fn(),
  getPresentationState: jest.fn(),
  handleContentDrop: jest.fn(),
};
const mockPrismaService = { userReference: { findUnique: jest.fn() } };
const mockIoServer = { to: jest.fn().mockReturnThis(), emit: jest.fn() };

describe('ContentGateway', () => {
  let gateway: ContentGateway;
  let module: TestingModule;

  const mockHandshake: Handshake = {
    headers: {},
    time: '',
    address: '',
    xdomain: false,
    secure: false,
    issued: 0,
    url: '',
    query: { sessionId: 'session-123' },
    auth: {},
  };
  const mockClientSocket: Partial<AuthenticatedSocket> = {
    handshake: mockHandshake,
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        ContentGateway,
        { provide: ContentService, useValue: mockContentService },
        { provide: PrismaService, useValue: mockPrismaService },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    gateway = module.get<ContentGateway>(ContentGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('handleContentControl', () => {
    it('should broadcast a slide update if user has permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: ['content:manage'],
      });
      const newState = { currentSlide: 1, totalSlides: 5, isActive: true };
      mockContentService.controlPresentation.mockResolvedValue(newState);

      await gateway.handleContentControl(
        { action: 'NEXT_SLIDE', idempotencyKey: 'k1' },
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockContentService.controlPresentation).toHaveBeenCalled();
      expect(mockIoServer.to).toHaveBeenCalledWith('session:session-123');
      expect(mockIoServer.emit).toHaveBeenCalledWith('slide.update', newState);
    });

    it('should throw ForbiddenException if user lacks permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: [],
      });

      await expect(
        gateway.handleContentControl(
          { action: 'NEXT_SLIDE', idempotencyKey: 'k1' },
          mockClientSocket as AuthenticatedSocket,
        ),
      ).rejects.toThrow(ForbiddenException);
    });
  });

  describe('handleRequestState', () => {
    it('should return the full presentation state directly to the requester', async () => {
      const fullState = {
        currentSlide: 2,
        totalSlides: 5,
        isActive: true,
        slideUrls: ['a', 'b'],
      };
      mockContentService.getPresentationState.mockResolvedValue(fullState);

      const result = await gateway.handleRequestState(
        mockClientSocket as AuthenticatedSocket,
      );

      expect(mockContentService.getPresentationState).toHaveBeenCalledWith(
        'session-123',
      );
      expect(result.success).toBe(true);
      expect(result.state).toEqual(fullState);
    });
  });
});
