import { InternalApiKeyGuard } from './internal-api-key.guard';
import { ConfigService } from '@nestjs/config';
import { ExecutionContext, UnauthorizedException } from '@nestjs/common';

describe('InternalApiKeyGuard', () => {
  let guard: InternalApiKeyGuard;
  let configService: ConfigService;

  beforeEach(() => {
    // Mock ConfigService
    configService = new ConfigService({ INTERNAL_API_KEY: 'secret-key' });
    guard = new InternalApiKeyGuard(configService);
  });

  it('should return true if the correct API key is provided', () => {
    const mockContext = {
      switchToHttp: () => ({
        getRequest: () => ({
          headers: { 'x-internal-api-key': 'secret-key' },
        }),
      }),
    } as ExecutionContext;

    expect(guard.canActivate(mockContext)).toBe(true);
  });

  it('should throw UnauthorizedException if the API key is incorrect', () => {
    const mockContext = {
      switchToHttp: () => ({
        getRequest: () => ({
          headers: { 'x-internal-api-key': 'wrong-key' },
        }),
      }),
    } as ExecutionContext;

    expect(() => guard.canActivate(mockContext)).toThrow(UnauthorizedException);
  });

  it('should throw UnauthorizedException if the API key is missing', () => {
    const mockContext = {
      switchToHttp: () => ({
        getRequest: () => ({
          headers: {}, // No key
        }),
      }),
    } as ExecutionContext;

    expect(() => guard.canActivate(mockContext)).toThrow(UnauthorizedException);
  });
});
