import { Test, TestingModule } from '@nestjs/testing';
import { UsersService } from './users.service';
import { PrismaService } from 'src/prisma.service';
import { MailerService } from '@nestjs-modules/mailer';
import { ConflictException } from '@nestjs/common';

jest.mock('bcrypt');

describe('UsersService', () => {
  let service: UsersService;
  let prisma: PrismaService;
  let module: TestingModule;

  // **FIX**: Define the mock provider object correctly
  const mockPrismaProvider = {
    user: {
      findUnique: jest.fn(),
      create: jest.fn(),
      update: jest.fn(),
      findMany: jest.fn(),
    },
    organization: { create: jest.fn() },
    role: { findFirst: jest.fn() },
    membership: { create: jest.fn() },
    $transaction: jest
      .fn()
      .mockImplementation(async (callback) => callback(mockPrismaProvider)),
  };

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        UsersService,
        {
          provide: PrismaService,
          useValue: mockPrismaProvider, // <-- Use the defined object
        },
        { provide: MailerService, useValue: { sendMail: jest.fn() } },
      ],
    }).compile();

    service = module.get<UsersService>(UsersService);
    prisma = module.get<PrismaService>(PrismaService);
  });

  afterAll(async () => {
    await module.close();
  });

  it('should throw ConflictException if user already exists', async () => {
    jest
      .spyOn(prisma.user, 'findUnique')
      .mockResolvedValue({ id: 'user-1' } as any);
    const registerDto = { email: 'test@example.com' } as any;
    await expect(service.create(registerDto)).rejects.toThrow(
      ConflictException,
    );
  });
});
