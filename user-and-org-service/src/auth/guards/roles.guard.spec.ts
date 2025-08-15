// In src/auth/guards/roles.guard.spec.ts
import { Test, TestingModule } from '@nestjs/testing';
import { RolesGuard } from './roles.guard';
import { Reflector } from '@nestjs/core';
import { PrismaService } from 'src/prisma.service';

describe('RolesGuard', () => {
  let guard: RolesGuard;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      providers: [
        RolesGuard,
        // Provide mock instances of the guard's dependencies
        { provide: Reflector, useValue: { get: jest.fn() } },
        { provide: PrismaService, useValue: {} },
      ],
    }).compile();

    guard = module.get<RolesGuard>(RolesGuard);
  });

  it('should be defined', () => {
    expect(guard).toBeDefined();
  });
});
