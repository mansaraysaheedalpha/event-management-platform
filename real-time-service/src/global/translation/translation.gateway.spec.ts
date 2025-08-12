import { Test, TestingModule } from '@nestjs/testing';
import { TranslationGateway } from './translation.gateway';
import { TranslationService } from './translation.service';
import { RequestTranslationDto } from '../dto/request-translation.dto';

const mockTranslationService = {
  getTranslation: jest.fn(),
};

describe('TranslationGateway', () => {
  let gateway: TranslationGateway;
  let module: TestingModule;

  beforeEach(async () => {
    module = await Test.createTestingModule({
      providers: [
        TranslationGateway,
        { provide: TranslationService, useValue: mockTranslationService },
      ],
    }).compile();
    gateway = module.get<TranslationGateway>(TranslationGateway);
    jest.clearAllMocks();
  });

  afterAll(async () => {
    await module.close();
  });

  it('should be defined', () => {
    expect(gateway).toBeDefined();
  });

  describe('handleTranslationRequest', () => {
    const dto: RequestTranslationDto = {
      messageId: 'msg-123',
      targetLanguage: 'kri',
    };
    const translatedText = 'Awa, di test pas!';

    it('should return a success response with the translated text', async () => {
      mockTranslationService.getTranslation.mockResolvedValue(translatedText);
      const result = await gateway.handleTranslationRequest(dto);

      expect(mockTranslationService.getTranslation).toHaveBeenCalledWith(
        dto.messageId,
        dto.targetLanguage,
      );

      // **FIX**: Test the entire shape of the success object at once.
      // This is cleaner and fully satisfies TypeScript's type checking.
      expect(result).toEqual({
        success: true,
        event: 'translation.response',
        data: {
          messageId: dto.messageId,
          targetLanguage: dto.targetLanguage,
          translatedText: translatedText,
        },
      });
    });

    it('should return a failure response if the service throws an error', async () => {
      const errorMessage = 'Translation service is unavailable.';
      mockTranslationService.getTranslation.mockRejectedValue(
        new Error(errorMessage),
      );
      const result = await gateway.handleTranslationRequest(dto);
      expect(result.success).toBe(false);
      expect(result.error).toBe(errorMessage);
    });
  });
});
