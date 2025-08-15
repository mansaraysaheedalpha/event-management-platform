import { Test, TestingModule } from '@nestjs/testing';
import { PermissionsService } from './permissions.service';
import { PrismaService } from 'src/prisma.service';
import { REDIS_CLIENT } from 'src/shared/redis.constants';

describe('PermissionsService', () => {
  let service: PermissionsService;
  let prisma: PrismaService;
  let redis: any;
  let module: TestingModule;

  // **FIX**: Define mock data inside the describe block
  const roleId = 'role-admin';
  const mockPermissionsList = ['users:create', 'users:read'];
  const mockPermissionsFromDb = [
    { name: 'users:create' },
    { name: 'users:read' },
  ];

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        PermissionsService,
        {
          provide: PrismaService,
          useValue: { role: { findUnique: jest.fn() } },
        },
        { provide: REDIS_CLIENT, useValue: { get: jest.fn(), set: jest.fn() } },
      ],
    }).compile();

    service = module.get<PermissionsService>(PermissionsService);
    prisma = module.get<PrismaService>(PrismaService);
    redis = module.get(REDIS_CLIENT);
  });

  afterAll(async () => {
    await module.close();
  });

  it('should return permissions from cache if available (cache hit)', async () => {
    const cachedData = JSON.stringify(mockPermissionsList);
    jest.spyOn(redis, 'get').mockResolvedValue(cachedData);

    const permissions = await service.getPermissionsForRole(roleId);

    expect(permissions).toEqual(mockPermissionsList);
    expect(redis.get).toHaveBeenCalledWith(`permissions:role:${roleId}`);
    expect(prisma.role.findUnique).not.toHaveBeenCalled();
  });

  it('should fetch permissions from DB and set cache on cache miss', async () => {
    jest.spyOn(redis, 'get').mockResolvedValue(null);
    jest
      .spyOn(prisma.role, 'findUnique')
      .mockResolvedValue({ permissions: mockPermissionsFromDb } as any);

    const permissions = await service.getPermissionsForRole(roleId);

    expect(permissions).toEqual(mockPermissionsList);
    expect(prisma.role.findUnique).toHaveBeenCalled();
    expect(redis.set).toHaveBeenCalledWith(
      `permissions:role:${roleId}`,
      JSON.stringify(mockPermissionsList),
      'EX',
      3600,
    );
  });
});
