//src/networking/huddles/huddles.gateway.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { HuddlesGateway } from './huddles.gateway';
import { HuddlesService } from './huddles.service';
import { EventRegistrationValidationService } from 'src/shared/services/event-registration-validation.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { HuddleResponseType } from './dto/respond-huddle.dto';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockHuddlesService = {
  createHuddle: jest.fn(),
  getHuddle: jest.fn(),
  getParticipant: jest.fn(),
  inviteToHuddle: jest.fn(),
  recordResponse: jest.fn(),
  checkAndConfirmHuddle: jest.fn(),
  leaveHuddle: jest.fn(),
  startHuddle: jest.fn(),
  completeHuddle: jest.fn(),
  cancelHuddle: jest.fn(),
  getActiveHuddles: jest.fn(),
  getUserHuddles: jest.fn(),
  buildInvitationPayload: jest.fn(),
};

const mockEventValidation = {
  validateEventRegistration: jest.fn(),
};

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('HuddlesGateway', () => {
  let gateway: HuddlesGateway;

  const mockClient = {
    handshake: { query: { sessionId: 'session-123' } },
    join: jest.fn(),
    leave: jest.fn(),
    emit: jest.fn(),
  } as any;

  const mockUser = { sub: 'user-1', email: 'test@example.com' };

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        HuddlesGateway,
        { provide: HuddlesService, useValue: mockHuddlesService },
        { provide: EventRegistrationValidationService, useValue: mockEventValidation },
      ],
    }).compile();

    gateway = module.get<HuddlesGateway>(HuddlesGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
    mockGetAuthenticatedUser.mockReturnValue(mockUser);
    mockEventValidation.validateEventRegistration.mockResolvedValue({ id: 'reg-1' });
  });

  describe('handleCreateHuddle', () => {
    it('should create a huddle and broadcast to event room', async () => {
      const newHuddle = {
        id: 'huddle-1',
        topic: 'Test Topic',
        problemStatement: 'Test problem',
        scheduledAt: new Date(),
        duration: 15,
        locationName: 'Room A',
        maxParticipants: 6,
        participants: [],
      };
      mockHuddlesService.createHuddle.mockResolvedValue(newHuddle);

      const result = await gateway.handleCreateHuddle(
        {
          topic: 'Test Topic',
          problemStatement: 'Test problem',
          eventId: 'event-1',
          scheduledAt: '2026-01-15T10:00:00Z',
          idempotencyKey: 'key-1',
        },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(result.huddleId).toBe('huddle-1');
      expect(mockEventValidation.validateEventRegistration).toHaveBeenCalledWith(
        'user-1',
        'event-1',
      );
      expect(mockHuddlesService.createHuddle).toHaveBeenCalled();
      expect(mockClient.join).toHaveBeenCalledWith('huddle:huddle-1');
      expect(mockIoServer.to).toHaveBeenCalledWith('event:event-1');
      expect(mockIoServer.emit).toHaveBeenCalledWith('huddle.created', expect.any(Object));
    });

    it('should return error if user not registered for event', async () => {
      mockEventValidation.validateEventRegistration.mockRejectedValue(
        new Error('Not registered'),
      );

      const result = await gateway.handleCreateHuddle(
        {
          topic: 'Test Topic',
          eventId: 'event-1',
          scheduledAt: '2026-01-15T10:00:00Z',
          idempotencyKey: 'key-1',
        },
        mockClient,
      );

      expect(result.success).toBe(false);
      expect(result.error).toBe('Not registered');
    });
  });

  describe('handleJoinHuddle', () => {
    it('should allow invited user to join huddle room', async () => {
      mockHuddlesService.getParticipant.mockResolvedValue({
        huddleId: 'huddle-1',
        userId: 'user-1',
        status: 'INVITED',
      });
      mockHuddlesService.getHuddle.mockResolvedValue({
        id: 'huddle-1',
        eventId: 'event-1',
      });

      const result = await gateway.handleJoinHuddle(
        { huddleId: 'huddle-1' },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(mockClient.join).toHaveBeenCalledWith('huddle:huddle-1');
    });

    it('should reject user not invited to huddle', async () => {
      mockHuddlesService.getParticipant.mockResolvedValue(null);

      const result = await gateway.handleJoinHuddle(
        { huddleId: 'huddle-1' },
        mockClient,
      );

      expect(result.success).toBe(false);
      expect(result.error).toContain('Not invited');
    });
  });

  describe('handleHuddleResponse', () => {
    it('should record accept response and notify participants', async () => {
      mockHuddlesService.recordResponse.mockResolvedValue({ success: true });
      mockHuddlesService.getHuddle.mockResolvedValue({
        id: 'huddle-1',
        participants: [
          { userId: 'user-1', status: 'ACCEPTED' },
          { userId: 'user-2', status: 'ACCEPTED' },
        ],
      });
      mockHuddlesService.checkAndConfirmHuddle.mockResolvedValue(false);

      const result = await gateway.handleHuddleResponse(
        { huddleId: 'huddle-1', response: HuddleResponseType.ACCEPT },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(mockIoServer.to).toHaveBeenCalledWith('huddle:huddle-1');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'huddle.participant_joined',
        expect.objectContaining({
          huddleId: 'huddle-1',
          userId: 'user-1',
          totalConfirmed: 2,
        }),
      );
    });

    it('should emit confirmation when min participants reached', async () => {
      mockHuddlesService.recordResponse.mockResolvedValue({ success: true });
      mockHuddlesService.getHuddle.mockResolvedValue({
        id: 'huddle-1',
        participants: [
          { userId: 'user-1', status: 'ACCEPTED' },
          { userId: 'user-2', status: 'ACCEPTED' },
        ],
      });
      mockHuddlesService.checkAndConfirmHuddle.mockResolvedValue(true);

      await gateway.handleHuddleResponse(
        { huddleId: 'huddle-1', response: HuddleResponseType.ACCEPT },
        mockClient,
      );

      expect(mockIoServer.emit).toHaveBeenCalledWith('huddle.confirmed', {
        huddleId: 'huddle-1',
      });
    });

    it('should emit error when huddle is full', async () => {
      mockHuddlesService.recordResponse.mockResolvedValue({
        success: false,
        huddleFull: true,
        error: 'Huddle is full',
        message: 'This huddle is now full.',
      });

      const result = await gateway.handleHuddleResponse(
        { huddleId: 'huddle-1', response: HuddleResponseType.ACCEPT },
        mockClient,
      );

      expect(result.success).toBe(false);
      expect(mockClient.emit).toHaveBeenCalledWith(
        'huddle.response_error',
        expect.objectContaining({
          huddleFull: true,
        }),
      );
    });

    it('should handle decline without notifying others', async () => {
      mockHuddlesService.recordResponse.mockResolvedValue({ success: true });

      const result = await gateway.handleHuddleResponse(
        { huddleId: 'huddle-1', response: HuddleResponseType.DECLINE },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(mockHuddlesService.getHuddle).not.toHaveBeenCalled();
    });
  });

  describe('handleInviteToHuddle', () => {
    it('should invite users and emit invitations', async () => {
      mockHuddlesService.inviteToHuddle.mockResolvedValue({
        invited: ['user-2', 'user-3'],
        alreadyInvited: [],
      });
      mockHuddlesService.buildInvitationPayload.mockResolvedValue({
        huddleId: 'huddle-1',
        topic: 'Test',
        scheduledAt: new Date(),
        duration: 15,
        currentParticipants: 1,
        maxParticipants: 6,
        confirmedAttendees: [],
      });

      const result = await gateway.handleInviteToHuddle(
        { huddleId: 'huddle-1', userIds: ['user-2', 'user-3'] },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(result.invited).toEqual(['user-2', 'user-3']);
      expect(mockIoServer.to).toHaveBeenCalledWith('user:user-2');
      expect(mockIoServer.to).toHaveBeenCalledWith('user:user-3');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'huddle.invitation',
        expect.any(Object),
      );
    });
  });

  describe('handleLeaveHuddle', () => {
    it('should allow user to leave and notify participants', async () => {
      mockHuddlesService.leaveHuddle.mockResolvedValue(undefined);
      mockHuddlesService.getHuddle.mockResolvedValue({
        id: 'huddle-1',
        participants: [{ userId: 'user-2', status: 'ACCEPTED' }],
      });

      const result = await gateway.handleLeaveHuddle(
        { huddleId: 'huddle-1' },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(mockClient.leave).toHaveBeenCalledWith('huddle:huddle-1');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'huddle.participant_left',
        expect.objectContaining({
          huddleId: 'huddle-1',
          userId: 'user-1',
        }),
      );
    });
  });

  describe('handleCancelHuddle', () => {
    it('should cancel huddle and notify all participants', async () => {
      mockHuddlesService.getHuddle.mockResolvedValue({
        id: 'huddle-1',
        participants: [
          { userId: 'user-1' },
          { userId: 'user-2' },
        ],
      });
      mockHuddlesService.cancelHuddle.mockResolvedValue(undefined);

      const result = await gateway.handleCancelHuddle(
        { huddleId: 'huddle-1', reason: 'Changed plans' },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(mockIoServer.to).toHaveBeenCalledWith('huddle:huddle-1');
      expect(mockIoServer.emit).toHaveBeenCalledWith(
        'huddle.cancelled',
        expect.objectContaining({
          huddleId: 'huddle-1',
          reason: 'Changed plans',
        }),
      );
    });
  });

  describe('handleListHuddles', () => {
    it('should return active huddles for an event', async () => {
      mockHuddlesService.getActiveHuddles.mockResolvedValue([
        {
          id: 'huddle-1',
          topic: 'Topic 1',
          scheduledAt: new Date(),
          duration: 15,
          status: 'FORMING',
          maxParticipants: 6,
          participants: [{ status: 'ACCEPTED' }],
        },
      ]);

      const result = await gateway.handleListHuddles(
        { eventId: 'event-1' },
        mockClient,
      );

      expect(result.success).toBe(true);
      expect(result.huddles).toHaveLength(1);
      expect(result.huddles[0].currentParticipants).toBe(1);
    });
  });

  describe('handleMyHuddles', () => {
    it('should return user huddles', async () => {
      mockHuddlesService.getUserHuddles.mockResolvedValue([
        {
          status: 'ACCEPTED',
          huddle: {
            id: 'huddle-1',
            topic: 'Topic',
            scheduledAt: new Date(),
            duration: 15,
            status: 'CONFIRMED',
            maxParticipants: 6,
            participants: [{}],
          },
        },
      ]);

      const result = await gateway.handleMyHuddles({}, mockClient);

      expect(result.success).toBe(true);
      expect(result.huddles).toHaveLength(1);
      expect(result.huddles[0].myStatus).toBe('ACCEPTED');
    });
  });

  describe('authentication', () => {
    it('should require authenticated user for all operations', async () => {
      mockGetAuthenticatedUser.mockImplementation(() => {
        throw new Error('Not authenticated');
      });

      const result = await gateway.handleCreateHuddle(
        {
          topic: 'Test',
          eventId: 'event-1',
          scheduledAt: '2026-01-15T10:00:00Z',
          idempotencyKey: 'key-1',
        },
        mockClient,
      );

      expect(result.success).toBe(false);
      expect(result.error).toBe('Not authenticated');
    });
  });
});
