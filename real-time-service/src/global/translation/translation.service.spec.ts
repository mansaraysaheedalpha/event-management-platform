import { Test, TestingModule } from '@nestjs/testing';
import { TranslationService } from './translation.service';
import { PrismaService } from 'src/prisma.service';
import { HttpService } from '@nestjs/axios';
import { ConfigService } from '@nestjs/config';
import { REDIS_CLIENT } from 'src/shared/redis.constants';
import { NotFoundException } from '@nestjs/common';
import { of, throwError } from 'rxjs';
import { AxiosError, AxiosResponse } from 'axios';

const mockPrisma = { message: { findUnique: jest.fn() } };
const mockHttp = { post: jest.fn() };
const mockConfig = { get: jest.fn().mockReturnValue('test-api-key') };
const mockRedis = { get: jest.fn(), set: jest.fn() };

const messageId = 'msg-123';
const originalText = 'Hello';
const translatedText = 'Bonjour';
const targetLanguage = 'fr';

describe('TranslationService', () => {
  let service: TranslationService;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        TranslationService,
        { provide: PrismaService, useValue: mockPrisma },
        { provide: HttpService, useValue: mockHttp },
        { provide: ConfigService, useValue: mockConfig },
        { provide: REDIS_CLIENT, useValue: mockRedis },
      ],
    }).compile();
    service = module.get<TranslationService>(TranslationService);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  it('should return a translation from the cache if it exists (cache hit)', async () => {
    mockRedis.get.mockResolvedValue(translatedText);
    const result = await service.getTranslation(messageId, targetLanguage);
    expect(result).toBe(translatedText);
    expect(mockPrisma.message.findUnique).not.toHaveBeenCalled();
    expect(mockHttp.post).not.toHaveBeenCalled();
  });

  it('should fetch from the API and cache the result on a cache miss', async () => {
    mockRedis.get.mockResolvedValue(null);
    mockPrisma.message.findUnique.mockResolvedValue({ text: originalText });
    const apiResponse: AxiosResponse = {
      data: { data: { translations: [{ translatedText }] } },
      status: 200,
      statusText: 'OK',
      headers: {},
      config: {} as any,
    };
    mockHttp.post.mockReturnValue(of(apiResponse));

    const result = await service.getTranslation(messageId, targetLanguage);
    expect(result).toBe(translatedText);
    expect(mockRedis.set).toHaveBeenCalledWith(
      `translation:${messageId}:${targetLanguage}`,
      translatedText,
      'EX',
      3600,
    );
  });

  it('should return the original text if the external API fails', async () => {
    mockRedis.get.mockResolvedValue(null);
    mockPrisma.message.findUnique.mockResolvedValue({ text: originalText });
    mockHttp.post.mockReturnValue(
      throwError(() => new AxiosError('API is down')),
    );

    const result = await service.getTranslation(messageId, targetLanguage);
    expect(result).toBe(originalText);
    // **FIX**: The test assertion is now correct because the service logic is fixed.
    expect(mockRedis.set).not.toHaveBeenCalled();
  });

  it('should throw NotFoundException if the original message is not in the database', async () => {
    mockRedis.get.mockResolvedValue(null);
    mockPrisma.message.findUnique.mockResolvedValue(null);
    await expect(
      service.getTranslation(messageId, targetLanguage),
    ).rejects.toThrow(NotFoundException);
  });
});
