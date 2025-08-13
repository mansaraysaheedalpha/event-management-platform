import { Test, TestingModule } from '@nestjs/testing';
import { SecurityGateway } from './security.gateway';
import { SecurityService } from './security.service';
import { getAuthenticatedUser } from 'src/common/utils/auth.utils';
import { ForbiddenException } from '@nestjs/common';

jest.mock('src/common/utils/auth.utils');
const mockGetAuthenticatedUser = getAuthenticatedUser as jest.Mock;

describe('SecurityGateway', () => {
  let gateway: SecurityGateway;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [SecurityGateway, { provide: SecurityService, useValue: {} }],
    }).compile();
    gateway = module.get<SecurityGateway>(SecurityGateway);
  });

  it('handleJoinSecurityStream should throw ForbiddenException if user lacks permission', () => {
    const mockClient = { join: jest.fn() } as any;
    mockGetAuthenticatedUser.mockReturnValue({
      sub: 'user-1',
      permissions: [],
    });
    expect(() => gateway.handleJoinSecurityStream(mockClient)).toThrow(
      ForbiddenException,
    );
  });
});
