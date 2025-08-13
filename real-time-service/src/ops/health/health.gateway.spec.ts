import { Test, TestingModule } from '@nestjs/testing';
import { HealthGateway } from './health.gateway';
import { HealthService } from './health.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { ForbiddenException } from '@nestjs/common';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

const mockIoServer = {
  to: jest.fn().mockReturnThis(),
  emit: jest.fn(),
};

describe('HealthGateway', () => {
  let gateway: HealthGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [HealthGateway, { provide: HealthService, useValue: {} }],
    }).compile();
    gateway = module.get<HealthGateway>(HealthGateway);
    (gateway as any).server = mockIoServer;
    jest.clearAllMocks();
  });

  describe('handleJoinHealthStream', () => {
    const mockClient = { join: jest.fn() } as any;

    it('should allow a user with permission to join the health room', async () => {
      const mockAdmin = {
        sub: 'super-admin',
        permissions: ['system:health:read'],
      };
      mockGetAuthenticatedUser.mockReturnValue(mockAdmin);

      await gateway.handleJoinHealthStream(mockClient);
      expect(mockClient.join).toHaveBeenCalledWith('system-health');
    });

    it('should throw ForbiddenException if user lacks permission', async () => {
      mockGetAuthenticatedUser.mockReturnValue({
        sub: 'user-1',
        permissions: [],
      });
      await expect(gateway.handleJoinHealthStream(mockClient)).rejects.toThrow(
        ForbiddenException,
      );
    });
  });
});
