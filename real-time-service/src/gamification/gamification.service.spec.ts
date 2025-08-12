import { Test, TestingModule } from '@nestjs/testing';
import { GamificationService } from './gamification.service';
import { PrismaService } from 'src/prisma.service';
import { GamificationGateway } from './gamification.gateway';

const mockPrisma = {
  $transaction: jest.fn().mockImplementation((cb) => cb(mockPrisma)),
  gamificationPointEntry: {
    create: jest.fn(),
    aggregate: jest.fn(),
    groupBy: jest.fn(),
    count: jest.fn(),
  },
  userReference: { findMany: jest.fn() },
  gamificationAchievement: { findMany: jest.fn(), create: jest.fn() },
};
const mockGateway = {
  sendPointsAwardedNotification: jest.fn(),
  sendAchievementNotification: jest.fn(),
  broadcastLeaderboardUpdate: jest.fn(),
};

describe('GamificationService', () => {
  let service: GamificationService;
  let module: TestingModule; // **Step 1: Declare the module variable**

  beforeEach(async () => {
    // **Step 2: Assign the compiled module to the variable**
    module = await Test.createTestingModule({
      providers: [
        GamificationService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: GamificationGateway, useValue: mockGateway },
      ],
    }).compile();
    service = module.get<GamificationService>(GamificationService);
    jest.clearAllMocks();
  });

  // **Step 3: Add this block to gracefully close the module after all tests**
  afterAll(async () => {
    await module.close();
  });

  describe('awardPoints', () => {
    it('should award points and check for achievements', async () => {
      mockPrisma.gamificationPointEntry.aggregate.mockResolvedValue({
        _sum: { points: 10 },
      });
      mockPrisma.gamificationAchievement.findMany.mockResolvedValue([]);
      mockPrisma.gamificationPointEntry.count.mockResolvedValue(1);

      const newTotalScore = await service.awardPoints(
        'user-1',
        'session-1',
        'QUESTION_ASKED',
      );

      expect(mockPrisma.gamificationPointEntry.create).toHaveBeenCalled();
      expect(newTotalScore).toBe(10);

      await new Promise(process.nextTick);
      expect(mockGateway.sendPointsAwardedNotification).toHaveBeenCalled();
      expect(mockGateway.broadcastLeaderboardUpdate).toHaveBeenCalled();
      expect(mockPrisma.gamificationAchievement.findMany).toHaveBeenCalled();
    });

    it('should grant a score-based achievement', async () => {
      const newTotalScore = 60;
      mockPrisma.gamificationPointEntry.aggregate.mockResolvedValue({
        _sum: { points: newTotalScore },
      });
      mockPrisma.gamificationAchievement.findMany.mockResolvedValue([]);

      await service.awardPoints('user-1', 'session-1', 'MESSAGE_SENT');
      await new Promise(process.nextTick);

      expect(mockPrisma.gamificationAchievement.create).toHaveBeenCalledWith({
        data: expect.objectContaining({ badgeName: 'Engaged Attendee' }),
      });
      expect(mockGateway.sendAchievementNotification).toHaveBeenCalled();
    });
  });

  describe('getLeaderboard', () => {
    it('should calculate and return the leaderboard with the current user rank', async () => {
      const userScores = [
        { userId: 'user-1', _sum: { points: 100 } },
        { userId: 'user-2', _sum: { points: 90 } },
        { userId: 'user-3', _sum: { points: 80 } },
      ];
      const userDetails = [
        { id: 'user-1', firstName: 'A', lastName: 'A' },
        { id: 'user-2', firstName: 'B', lastName: 'B' },
        { id: 'user-3', firstName: 'C', lastName: 'C' },
      ];
      mockPrisma.gamificationPointEntry.groupBy.mockResolvedValue(userScores);
      mockPrisma.userReference.findMany.mockResolvedValue(userDetails);

      const result = await service.getLeaderboard('session-1', 'user-2');

      expect(result.topEntries.length).toBe(3);
      expect(result.topEntries[0].rank).toBe(1);
      expect(result.topEntries[0].score).toBe(100);

      // **FIX**: Add null check before accessing properties
      expect(result.currentUser).not.toBeNull();
      if (result.currentUser) {
        expect(result.currentUser.rank).toBe(2);
        expect(result.currentUser.score).toBe(90);
      }
    });
  });
});
