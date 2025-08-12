import { Test, TestingModule } from '@nestjs/testing';
import { TeamsService } from './teams.service';
import { PrismaService } from 'src/prisma.service';
import { IdempotencyService } from 'src/shared/services/idempotency.service';
import { NotFoundException } from '@nestjs/common';

const mockPrisma = {
  $transaction: jest.fn().mockImplementation((cb) => cb(mockPrisma)),
  team: { create: jest.fn(), findUnique: jest.fn() },
  teamMembership: {
    create: jest.fn(),
    findFirst: jest.fn(),
    delete: jest.fn(),
  },
};
const mockIdempotency = { checkAndSet: jest.fn() };

const mockUser = { id: 'user-1' };
const mockSessionId = 'session-1';
const mockTeam = { id: 'team-1', name: 'Test Team', sessionId: mockSessionId };

describe('TeamsService', () => {
  let service: TeamsService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        TeamsService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: IdempotencyService, useValue: mockIdempotency },
      ],
    }).compile();
    // **FIX**: Pass the class name to module.get()
    service = module.get<TeamsService>(TeamsService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  describe('createTeam', () => {
    it('should create a team and add the creator as a member', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      mockPrisma.team.create.mockResolvedValue(mockTeam);
      mockPrisma.team.findUnique.mockResolvedValue(mockTeam);

      await service.createTeam(mockUser.id, mockSessionId, {
        name: 'Test',
        idempotencyKey: 'k1',
      });

      expect(mockPrisma.$transaction).toHaveBeenCalled();
      expect(mockPrisma.team.create).toHaveBeenCalled();
      expect(mockPrisma.teamMembership.create).toHaveBeenCalledWith({
        data: { userId: mockUser.id, teamId: mockTeam.id },
      });
    });
  });

  describe('joinTeam', () => {
    it('should allow a user to switch teams within a session', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      mockPrisma.team.findUnique.mockResolvedValue(mockTeam);
      const existingMembership = { userId: mockUser.id, teamId: 'old-team-id' };
      mockPrisma.teamMembership.findFirst.mockResolvedValue(existingMembership);

      await service.joinTeam(mockUser.id, {
        teamId: mockTeam.id,
        idempotencyKey: 'k2',
      });

      expect(mockPrisma.$transaction).toHaveBeenCalled();
      expect(mockPrisma.teamMembership.delete).toHaveBeenCalledWith({
        where: {
          userId_teamId: {
            userId: mockUser.id,
            teamId: existingMembership.teamId,
          },
        },
      });
      expect(mockPrisma.teamMembership.create).toHaveBeenCalledWith({
        data: { userId: mockUser.id, teamId: mockTeam.id },
      });
    });

    it('should throw NotFoundException if team does not exist', async () => {
      mockIdempotency.checkAndSet.mockResolvedValue(true);
      mockPrisma.team.findUnique.mockResolvedValue(null);
      await expect(
        service.joinTeam(mockUser.id, {
          teamId: 'fake-id',
          idempotencyKey: 'k3',
        }),
      ).rejects.toThrow(NotFoundException);
    });
  });
});
